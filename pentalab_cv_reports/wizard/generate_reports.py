from odoo import models, fields, api
from datetime import datetime, date
import calendar
import zipfile
import base64
import io
import unicodedata
from collections import defaultdict
from odoo.tools.misc import xlsxwriter

class generateReportsWizard(models.TransientModel):
    _name = 'generate.reports.wizard'
    _description = 'Wizard to generate reports'

    report_type = fields.Selection(
        [('purchase', 'Purchase'), ('uafe', 'UAFE')],
        string='Report Type',
        default='purchase',
        required=True,
        help='Select the type of report to generate.'
    )
    date_start = fields.Date(string='Date start')
    date_end = fields.Date(string='Date end')
    year = fields.Selection(
        selection=lambda self: [(str(y), str(y)) for y in range(datetime.now().year - 5, datetime.now().year + 2)],
        string='Year',
        default=lambda self: str(datetime.now().year),
    )
    month = fields.Selection(
        selection=[
            ('01', 'January'), ('02', 'February'), ('03', 'March'), ('04', 'April'),
            ('05', 'May'), ('06', 'June'), ('07', 'July'), ('08', 'August'),
            ('09', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
        ],
        string='Month',
        default=lambda self: datetime.now().strftime('%m'),
    )
    domain_uafe = fields.Selection(
        selection=[
            ('customer', 'Customer'),
            ('supplier', 'Supplier'),
            ('customer_supplier', 'Customer/Supplier')
        ],
        string='Domain',
        default='customer'
    )
    # campos UAFE
    total_reg_clientes = fields.Integer(string='Total Clientes Registrados', readonly=True)
    total_reg_operaciones = fields.Integer(string='Total Operaciones Registradas', readonly=True)
    total_reg_transacciones = fields.Integer(string='Total Transacciones Registradas', readonly=True)
    total_operaciones = fields.Integer(string='Total de Operaciones', readonly=True)
    total_debitos = fields.Integer(string='Total Débitos', readonly=True)
    total_creditos = fields.Integer(string='Total Créditos', readonly=True)
    total_efectivo = fields.Integer(string='Total en Efectivo', readonly=True)
    total_cheque = fields.Integer(string='Total en Cheque', readonly=True)
    total_tarjeta = fields.Integer(string='Total en Tarjeta', readonly=True)
    total_valores_bienes = fields.Integer(string='Total Valores y Bienes', readonly=True)
    total_valor_total = fields.Integer(string='Total General', readonly=True)
    
    def remove_accents(self, texto):
        return ''.join(
            c for c in unicodedata.normalize('NFKD', texto)
            if not unicodedata.combining(c)
        )
    
    def sanitize_text(self, text):
        if not text:
            return ''
        # Quitar tildes
        text = self.remove_accents(text)
        # Quitar guiones y caracteres especiales (mantener letras, números y espacios)
        import re
        text = re.sub(r'[^A-Za-z0-9\s]', '', text)
        # Opcional: convertir a mayúsculas
        return text.upper().strip()
    
    def get_invoices_from_payments(self, date_start, date_end, uafe_domain=None):
        # 1️⃣ Todos los pagos validados en el rango de fechas
        payments = self.env['account.payment'].search([
            ('date', '>=', date_start),
            ('date', '<=', date_end),
            ('state', '=', 'posted')
        ])
        # 2️⃣ Pagos que tengan facturas directas
        direct_invoice_payments = payments.filtered(lambda p: p.invoice_ids)
        # 3️⃣ Obtener facturas directas de esos pagos
        invoices_from_direct_payments = direct_invoice_payments.mapped('invoice_ids')
        # 4️⃣ Facturas desde líneas contables relacionadas a pagos (POS o asientos contables)
        move_lines = payments.mapped('move_line_ids')
        invoice_lines = move_lines.filtered(lambda l: l.move_id.move_type in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund'])
        invoices_from_lines = invoice_lines.mapped('move_id')
        # 5️⃣ Combinar todas las facturas y eliminar duplicados
        all_invoices = (invoices_from_direct_payments | invoices_from_lines)
        # 6️⃣ Filtrar según uafe_domain
        if uafe_domain == 'customer':
            all_invoices = all_invoices.filtered(lambda inv: inv.partner_id.customer_rank > 0)
        elif uafe_domain == 'supplier':
            all_invoices = all_invoices.filtered(lambda inv: inv.partner_id.supplier_rank > 0)
        # cualquier otro valor o None → no filtra, devuelve ambos
        # 7️⃣ Ordenar por fecha
        all_invoices = all_invoices.sorted(key=lambda inv: inv.date)
        return all_invoices

    
    def get_payments_and_invoices(self, date_start, date_end, uafe_domain):
        # Definir filtros según uafe_domain
        if uafe_domain == "customer":
            partner_domain = [('partner_id.customer_rank', '>', 0)]
            invoice_types = ['out_invoice']
        elif uafe_domain == "supplier":
            partner_domain = [('partner_id.supplier_rank', '>', 0)]
            invoice_types = ['in_invoice']
        else:
            partner_domain = ['|', ('partner_id.customer_rank', '>', 0), ('partner_id.supplier_rank', '>', 0)]
            invoice_types = ['out_invoice', 'in_invoice']
        # -------------------
        # 1. Facturas en el rango y con partner filtrado
        # -------------------
        invoices = self.env['account.move'].search(
            [('date', '>=', date_start),
            ('date', '<=', date_end),
            ('state', '=', 'posted'),
            ('move_type', 'in', invoice_types)] + partner_domain
        )
        # -------------------
        # 5. Retornar resultados
        # -------------------
        return invoices

    def _get_invoices_data(self):
        # Generar data para reporte
        account_move = self.env['account.move']
        domain = [
            ('state', '=', 'posted'),
            ('move_type', '=', 'out_invoice'),
        ]
        if self.report_type == 'uafe':
            sales_amount_threshold = self.env.company.sales_amount_report_uafe or 0.0
            year = int(self.year)
            month = int(self.month)
            last_day = calendar.monthrange(year, month)[1]
            domain += [
                ('invoice_date', '>=', date(year, month, 1)),
                ('invoice_date', '<=', date(year, month, last_day)),
            ]
            if self.domain_uafe == 'customer':
                domain += [('partner_id.customer_rank', '>', 0)]
            elif self.domain_uafe == 'supplier':
                domain += [('partner_id.supplier_rank', '>', 0)]
            invoices = account_move.search(domain, order='invoice_date asc')
            invoices = invoices.filtered(lambda inv: any(
                line.product_id.categ_id.divide_quantity
                for line in inv.invoice_line_ids
            ))
            # nueva logica
            new_invoices = self.get_payments_and_invoices(date(year, month, 1), date(year, month, last_day), self.domain_uafe)
            new2_invoices = self.get_invoices_from_payments(date(year, month, 1), date(year, month, last_day), self.domain_uafe)
            print("======= LENS ======")
            print(len(invoices))
            print(len(new_invoices))
            print(len(new2_invoices))
            print("===================")
            if sales_amount_threshold > 0.0:
                # Agrupar y sumar por proveedor
                partner_totals = defaultdict(float)
                partner_invoices = defaultdict(list)
                for inv in invoices:
                    partner_id = inv.partner_id.id
                    partner_totals[partner_id] += inv.amount_total
                    partner_invoices[partner_id].append(inv)
                # Filtrar proveedores cuya suma supere el monto configurado
                filtered_invoices = account_move
                for partner_id, total in partner_totals.items():
                    if partner_id in (30487, 30588):
                        print("Partner ID: %s" % partner_id)
                        print("Partner Name: %s" % self.env['res.partner'].browse(partner_id).name)
                        print("Total: %s" % total)
                        print("==============")
                    if total >= sales_amount_threshold:
                        filtered_invoices += account_move.browse([inv.id for inv in partner_invoices[partner_id]])
                return filtered_invoices
            else:
                return invoices
        else:
            domain += [
                ('invoice_date', '>=', self.date_start),
                ('invoice_date', '<=', self.date_end),
            ]
            return account_move.search(domain, order='invoice_date asc')
        
    def _get_retentions_data(self, invoice):
        # Obtener datos de retenciones de la factura
        data = invoice.l10n_ec_action_view_withholds()
        move_obj = self.env['account.move']
        if data and data['res_id']:
            retentions = move_obj.browse(data['res_id'])
        else:
            retentions = move_obj
        return retentions
    
    def _get_identification_type(self, value):
        if not value or not isinstance(value, str):
            return ''
        v = self.remove_accents(value).lower()
        if v.startswith('ruc'):
            return 'R'
        elif v.startswith('cedula'):
            return 'C'
        elif v.startswith('pasaporte'):
            return 'P'
        elif v.startswith('id extranjera'):
            return 'A'
    
    def print_report(self):
        if self.report_type == 'uafe':
            return self.generate_uafe_reports()
        return self.env.ref('pentalab_report.action_generate_reports_xlsx').report_action(self)
    
    def generate_uafe_reports(self):
        # Inicializar variables globales
        self.total_reg_clientes = 0
        self.total_reg_operaciones = 0
        self.total_reg_transacciones = 0
        self.total_operaciones = 0
        self.total_debitos = 0
        self.total_creditos = 0
        self.total_efectivo = 0
        self.total_cheque = 0
        self.total_tarjeta = 0
        self.total_valores_bienes = 0
        self.total_valor_total = 0
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            report_files = {
                'DETALLECLIENTE.xlsx': self._generate_detalle_cliente(),
                'DETALLEOPERACION.xlsx': self._generate_detalle_operacion(),
                'DETALLETRANSACCION.xlsx': self._generate_detalle_transaccion(),
                'CABECERA.xlsx': self._generate_cabecera(),
            }

            for filename, content in report_files.items():
                zip_file.writestr(filename, content)

        zip_buffer.seek(0)
        attachment = self.env['ir.attachment'].create({
            'name': 'UAFE_Reports.zip',
            'type': 'binary',
            'datas': base64.b64encode(zip_buffer.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/zip',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def _generate_detalle_cliente(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Detalle Cliente")
        # Ancho de columnas
        worksheet.set_column('A:A', 15)
        worksheet.set_column('B:B', 12)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 30)
        worksheet.set_column('E:E', 30)
        worksheet.set_column('F:F', 15)
        worksheet.set_column('G:G', 30)
        worksheet.set_column('H:H', 15)
        worksheet.set_column('I:I', 15)
        worksheet.set_column('J:J', 15)
        worksheet.set_column('K:K', 12)
        worksheet.set_column('L:L', 15)
        # Encabezados
        headers = ['COD_TIPO_PERSONA', 'COD_TIPO_ID', 'ID_CLIENTE', 'NOMBRES_RAZON_SOCIAL','APELLIDOS_NOMBRE_COMRECIAL', 'COD_PAIS_NACIONALIDAD',
                   'DIRECCION', 'COD_PROVINCIA', 'COD_CANTON', 'COD_PARROQUIA', 'COD_ACTIVIDAD_ECONOMICA', 'INGRESO_CLIENTE']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        # Obtener facturas entre fechas
        invoiced_data = {}
        customers = self.env['res.partner']
        invoices = self._get_invoices_data()
        # Mapear clientes y valores facturados
        for invoice in invoices:
            if invoice.partner_id not in customers:
                customers |= invoice.partner_id
            if invoice.partner_id.id not in invoiced_data:
                invoiced_data[invoice.partner_id.id] = invoice.amount_total
            else:
                invoiced_data[invoice.partner_id.id] += invoice.amount_total
        # Enviar total clientes
        self.total_reg_clientes = len(customers)
        # Mapear datos de clientes
        for customer in customers:
            state =  str(customer.state_id.code).zfill(2) if customer.state_id and customer.state_id.code else ''
            city = str(customer.city_id.code).zfill(2) if customer.city_id and customer.city_id.code else ''
            parish = str(customer.parroquia_id.code).zfill(2) if customer.parroquia_id and customer.parroquia_id.code else ''
            row = worksheet.dim_rowmax + 1
            worksheet.write(row, 0, 'N' if customer.company_type == 'person' else 'J')
            worksheet.write(row, 1, self._get_identification_type(customer.l10n_latam_identification_type_id.name) or '')
            worksheet.write(row, 2, customer.vat or '')
            worksheet.write(row, 3, self.sanitize_text(customer.name) or '')
            worksheet.write(row, 4, self.sanitize_text(customer.display_name) or '')
            worksheet.write(row, 5, customer.country_id.code or '')
            worksheet.write(row, 6, self.sanitize_text(customer.street) or '')
            worksheet.write(row, 7, state)
            worksheet.write(row, 8, f"{state}{city}" if state and city else '')
            worksheet.write(row, 9, f"{state}{city}{parish}" if state and city and parish else '')
            worksheet.write(row, 10, customer.industry_id and customer.industry_id.code or '')
            worksheet.write(row, 11, int(invoiced_data.get(customer.id, 0.0)) or 0)
        workbook.close()
        output.seek(0)
        return output.read()
    
    def _generate_detalle_operacion(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Detalle Operacion")
        # Ancho de columnas
        worksheet.set_column('A:A', 15)
        worksheet.set_column('B:B', 12)
        worksheet.set_column('C:C', 17)
        worksheet.set_column('D:D', 25)
        worksheet.set_column('E:E', 25)
        worksheet.set_column('F:F', 30)
        worksheet.set_column('G:G', 20)
        worksheet.set_column('H:H', 17)
        worksheet.set_column('I:I', 17)
        worksheet.set_column('J:J', 30)
        worksheet.set_column('K:K', 30)
        worksheet.set_column('L:L', 30)
        worksheet.set_column('M:M', 30)
        worksheet.set_column('N:N', 20)
        worksheet.set_column('O:O', 20)
        worksheet.set_column('P:P', 15)
        worksheet.set_column('Q:Q', 15)
        worksheet.set_column('R:R', 17)
        worksheet.set_column('S:S', 17)
        worksheet.set_column('T:T', 20)
        # Encabezados
        headers = ['COD_TIPO_ID', 'ID_CLIENTE', 'NUMERO_OPERACION', 'COD_TIPO_OPEREACION', 'TIPO_FINANCIAMIENTO', 'VALOR_FINANCIAMIENTO_DIRECTO',
                   'VALOR_FINANCIAMIENTO_EXTERNO', 'VALOR_TOTAL_OPERACION', 'FECHA_OPERACION', 'ANIO_FABRICACION', 'COD_TIPO_VEHICULO_MAQUINARIA',
                   'MODELO_VEHICULO_MAQUINARIA', 'MARCA_VEHICULO_MAQUINARIA', 'NUMERO_CHASIS_VEHICULO_MAQUINARIA', 'CILINDRAJE_VEHICULO',
                   'COD_NIVEL_BLINDAJE', 'CONDICION_BIEN', 'NUMERO_PLACA', 'COD_PROV_OPERACION', 'COD_CANTON_OPERACION', 'COD_PARROQUIA_OPERACION']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        # Obtener facturas entre fechas
        invoices = self._get_invoices_data()
        operation_count = 0
        for invoice in invoices:
            customer = invoice.partner_id
            state =  str(customer.state_id.code).zfill(2) if customer.state_id and customer.state_id.code else ''
            city = str(customer.city_id.code).zfill(2) if customer.city_id and customer.city_id.code else ''
            parish = str(customer.parroquia_id.code).zfill(2) if customer.parroquia_id and customer.parroquia_id.code else ''
            for line in invoice.invoice_line_ids:
                unit_price = line.price_subtotal / line.quantity if line.quantity else 0
                quantity = int(line.quantity)
                partial_total = 0  # Para controlar el total acumulado
                # Si es rastreable por numeros de serie
                serial_numbers = self.env['stock.lot']
                if line.product_id.is_storable and line.product_id.tracking == 'serial':
                    serial_numbers = invoice.stock_lot_ids.filtered(lambda l, product=line.product_id: l.product_id == product)
                for i in range(quantity):
                    if i == quantity - 1:
                        price = round(line.price_subtotal - partial_total, 2)
                    else:
                        price = round(unit_price, 2)
                        partial_total += price
                    serial_number = serial_numbers[i].name if i < len(serial_numbers) else ''
                    row = worksheet.dim_rowmax + 1
                    worksheet.write(row, 0, self._get_identification_type(invoice.partner_id.l10n_latam_identification_type_id.name) or '')
                    worksheet.write(row, 1, invoice.partner_id.vat or '')
                    worksheet.write(row, 2, self.sanitize_text(invoice.name) or '')
                    worksheet.write(row, 3, 'VEN')
                    worksheet.write(row, 4, 'NAP')
                    worksheet.write(row, 5, '0')
                    worksheet.write(row, 6, '0')
                    worksheet.write(row, 7, price or 0)
                    self.total_operaciones += price or 0
                    format_date = invoice.invoice_date.strftime('%Y%m%d') if invoice.invoice_date else ''
                    worksheet.write(row, 8, format_date)
                    # Mapear datos vacios
                    worksheet.write(row, 9, '')
                    worksheet.write(row, 10, '')
                    worksheet.write(row, 11, '')
                    worksheet.write(row, 12, self.sanitize_text(line.product_id.product_brand_id.name) if line.product_id.product_brand_id else '')
                    # CHASIS - N LOTE
                    worksheet.write(row, 13, serial_number)
                    worksheet.write(row, 14, '')
                    worksheet.write(row, 15, 'NO')
                    worksheet.write(row, 16, 'N')
                    worksheet.write(row, 17, 'NO APLICA')
                    # Atributos del producto
                    for atrib in line.product_id.product_template_attribute_value_ids:
                        if atrib.attribute_id.name == 'Año':
                            worksheet.write(row, 9, self.sanitize_text(atrib.name) or '')
                        elif atrib.attribute_id.name == 'Modelo Homologado ANT':
                            worksheet.write(row, 11, self.sanitize_text(atrib.name) or '')
                        elif atrib.attribute_id.name == 'Cilindraje':
                            worksheet.write(row, 14, self.sanitize_text(atrib.name) or '')
                    worksheet.write(row, 18, state)
                    worksheet.write(row, 19, f"{state}{city}" if state and city else '')
                    worksheet.write(row, 20, f"{state}{city}{parish}" if state and city and parish else '')
                    operation_count += 1
        self.total_reg_operaciones = operation_count
        workbook.close()
        output.seek(0)
        return output.read()
    
    def _generate_detalle_transaccion(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Detalle Transaccion")
        # Ancho de columnas
        worksheet.set_column('A:A', 15)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 20)
        worksheet.set_column('D:D', 20)
        worksheet.set_column('E:E', 22)
        worksheet.set_column('F:F', 22)
        worksheet.set_column('G:G', 15)
        worksheet.set_column('H:H', 15)
        worksheet.set_column('I:I', 15)
        worksheet.set_column('J:J', 15)
        worksheet.set_column('K:K', 22)
        worksheet.set_column('L:L', 22)
        worksheet.set_column('M:M', 15)
        worksheet.set_column('N:N', 17)
        worksheet.set_column('O:O', 17)
        worksheet.set_column('P:P', 15)
        worksheet.set_column('Q:Q', 17)
        worksheet.set_column('R:R', 15)
        worksheet.set_column('S:S', 15)
        worksheet.set_column('T:T', 25)
        worksheet.set_column('U:U', 22)
        worksheet.set_column('V:V', 20)
        worksheet.set_column('W:W', 30)
        worksheet.set_column('X:X', 30)
        # Encabezados
        headers = ['COD_TIPO_ID', 'ID_CLIENTE', 'NUMERO_OPERACION', 'FECHA_TRANSACCION', 'NUMERO_TRANSACCION', 'COD_TIPO_TRANSACCION', 'VALOR_DEBITO',
                   'VALOR_CREDITO', 'VALOR_EFECTIVO', 'VALOR_CHEQUE', 'VALOR_TARJETA_CREDITO', 'VALOR_TVALORES_BIENES', 'VALOR_TOTAL', 'COD_TIPO_MONEDA',
                   'CANTIDAD_BAD_50', 'MONTO_BAD_50', 'CANTIDAD_BAD_100', 'MONTO_BAD_100', 'COD_AGENCIA', 'COD_PAGO_COBRO_TERCEROS', 'COD_TIPO_ID_TERCEROS',
                   'ID_TERCEROS', 'NOMBRES_RAZON_SOCIAL_TERCEROS', 'APELLIDOS_RAZON_COMERCIAL_TERCEROS']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        # Obtener facturas entre fechas
        invoices = self._get_invoices_data()
        # Mapear pagos de facturas
        transaction_count = 0
        for invoice in invoices:
            move_payments = []
            # mapear pagos directos
            result = invoice.open_payments()
            payment_id = result.get('res_id')
            if isinstance(payment_id, int) and payment_id > 0:
                pay = self.env['account.payment'].browse(payment_id)
                move_payments.append(pay.move_id)
            # mapear pagos de asientos POS
            if invoice.invoice_payments_widget and invoice.invoice_payments_widget['content']:
                for pays in invoice.invoice_payments_widget['content']:
                    move_payments.append(pays['move_id'])
            for move_payment in move_payments:
                payment = self.env['account.move'].browse(move_payment)
                row = worksheet.dim_rowmax + 1
                worksheet.write(row, 0, self._get_identification_type(payment.partner_id.l10n_latam_identification_type_id.name) or '')
                worksheet.write(row, 1, payment.partner_id.vat or '')
                worksheet.write(row, 2, self.sanitize_text(invoice.name) or '')
                worksheet.write(row, 3, payment.date.strftime('%d/%m/%Y') if payment.date else '')
                worksheet.write(row, 4, self.sanitize_text(payment.name) or '')
                worksheet.write(row, 5, '192')
                payment_amount = abs(int(payment.amount_total))
                # cliente
                if invoice.move_type in ('out_invoice', 'out_refund'):
                    self.total_debitos += payment_amount
                # proveedor
                else:
                    self.total_creditos += payment_amount
                worksheet.write(row, 6, payment_amount if invoice.move_type in ('out_invoice', 'out_refund') else 0)
                worksheet.write(row, 7, payment_amount if invoice.move_type not in ('out_invoice', 'out_refund') else 0)
                worksheet.write(row, 8, '0')
                worksheet.write(row, 9, '0')
                worksheet.write(row, 10, '0')
                if payment.journal_id.type == 'cash':
                    worksheet.write(row, 8, payment_amount)
                    self.total_efectivo += payment_amount
                elif payment.journal_id.type == 'bank':
                    worksheet.write(row, 9, payment_amount)
                    self.total_cheque += payment_amount
                elif payment.journal_id.type == 'credit':
                    worksheet.write(row, 10, payment_amount)
                    self.total_tarjeta += payment_amount
                retention_total = 0
                # Retenciones
                retentions = self._get_retentions_data(invoice)
                for retention in retentions:
                    for line in retention.l10n_ec_withhold_line_ids:
                        for tax in line.tax_ids:
                            if tax.amount_type == 'percent':
                                retention_total += tax.amount
                self.total_valores_bienes += retention_total
                self.total_valor_total += payment_amount + retention_total
                worksheet.write(row, 11, retention_total)
                worksheet.write(row, 12, payment_amount + retention_total)
                worksheet.write(row, 13, self.sanitize_text(payment.currency_id.name))
                worksheet.write(row, 14, '0')
                worksheet.write(row, 15, '0')
                worksheet.write(row, 16, '0')
                worksheet.write(row, 17, '0')
                worksheet.write(row, 18, '259211002')
                worksheet.write(row, 19, 'PRS')
                worksheet.write(row, 20, 'N')
                worksheet.write(row, 21, 'NO APLICA')
                worksheet.write(row, 22, 'NO APLICA')
                worksheet.write(row, 23, 'NO APLICA')
                transaction_count += 1
        self.total_reg_transacciones = transaction_count
        workbook.close()
        output.seek(0)
        return output.read()
    
    def _generate_cabecera(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Detalle Transaccion")
        # Ancho de columnas
        worksheet.set_column('A:A', 15)
        worksheet.set_column('B:B', 17)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 20)
        worksheet.set_column('F:F', 20)
        worksheet.set_column('G:G', 20)
        worksheet.set_column('H:H', 20)
        worksheet.set_column('I:I', 15)
        worksheet.set_column('J:J', 15)
        worksheet.set_column('K:K', 15)
        worksheet.set_column('L:L', 15)
        worksheet.set_column('M:M', 15)
        worksheet.set_column('N:N', 15)
        worksheet.set_column('O:O', 15)
        # Encabezados
        headers = ['COD_REGISTRO', 'PERIODO_REPORTE', 'FECHA_REPORTE', 'COD_USUARIO', 'TOTAL_REG_CLIENTES', 'TOTAL_REG_OPERACIONES', 'TOTAL_REG_TRANSACCIONES',
                   'TOTAL_OPERACIONES', 'TOTAL_DEBITOS', 'TOTAL_CREDITOS', 'TOTAL_EFECTIVO', 'TOTAL_CHEQUE', 'TOTAL_TARJETA_CREDITO', 'TOTAL_TVALORES_BIENES',
                   'TOTAL_VALOR_TOTAL']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        worksheet.write(1, 0, '25921')
        worksheet.write(1, 1, self.month or '')
        worksheet.write(1, 2, datetime.today().strftime('%Y%m%d'))
        worksheet.write(1, 3, self.sanitize_text(self.env.user.login) or '')
        worksheet.write(1, 4, self.total_reg_clientes)
        worksheet.write(1, 5, self.total_reg_operaciones)
        worksheet.write(1, 6, self.total_reg_transacciones)
        worksheet.write(1, 7, self.total_operaciones)
        worksheet.write(1, 8, self.total_debitos)
        worksheet.write(1, 9, self.total_creditos)
        worksheet.write(1, 10, self.total_efectivo)
        worksheet.write(1, 11, self.total_cheque)
        worksheet.write(1, 12, self.total_tarjeta)
        worksheet.write(1, 13, self.total_valores_bienes)  # Si aplicas este en tu lógica
        worksheet.write(1, 14, self.total_valor_total)
        workbook.close()
        output.seek(0)
        return output.read()
    
class ReportA1Wizard(models.TransientModel):
    _name = 'report.a1.wizard'
    _description = 'Wizard to generate A1 report'
    
    def _get_selection_opcions(self):
        options = [('0', 'Todos')]
        types = self.env['l10n_latam.document.type'].search([('active', '=', True)])
        for t in types:
            options.append((str(t.id), t.name))
        return options
    
    date_start = fields.Date(string='Date start', required=True)
    date_end = fields.Date(string='Date end', required=True)
    document_type = fields.Selection(selection=lambda self: self._get_selection_opcions(), default='0', required=True)
    
    def print_report(self):
        return self.env.ref('pentalab_report.action_report_ventas_a1_xlsx').report_action(self)