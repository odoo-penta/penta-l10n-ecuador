from odoo import models, fields
from datetime import datetime, date
import calendar
import zipfile
import base64
import io
from collections import defaultdict
from odoo.tools.misc import xlsxwriter
from odoo.tools import remove_accents, sanitize_text

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
    
    def _total_payments_by_partner(self, moves):
        totals = {}
        processed = set()
        # Recorrer pagos tipo account.move
        for move in moves:
            for line in move.line_ids:
                matched_lines = line.matched_debit_ids | line.matched_credit_ids
                for matched in matched_lines:
                    # Identificador único para evitar duplicados
                    key = (matched.id,)
                    if key in processed:
                        continue
                    processed.add(key)
                    reconciled_line = matched.debit_move_id if matched.debit_move_id.move_id.move_type in ('out_invoice','in_invoice') else matched.credit_move_id
                    if reconciled_line.move_id.move_type in ('out_invoice','in_invoice'):
                        inv = reconciled_line.move_id
                        partner = inv.partner_id
                        totals.setdefault(partner.id, {'partner': partner, 'total': 0.0})
                        totals[partner.id]['total'] += matched.amount
        return totals
    
    def _get_data_for_reports(self, date_start, date_end, uafe_domain):
        # Filtrar facturas que tengan líneas con números de serie
        def _has_serial_number(inv):
            for line in inv.invoice_line_ids:
                if (
                    line.product_id.is_storable
                    and line.product_id.tracking in ('serial', 'lot')
                ):
                    return True
            return False
        # Definir filtros según uafe_domain
        m_partner_domain = ['|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
        if uafe_domain == "customer":
            m_partner_domain = [('customer_rank', '>', 0)]
        elif uafe_domain == "supplier":
            m_partner_domain = [('supplier_rank', '>', 0)]
        # Obtener asientos de pagos entre fechas y con facturas relacinadas
        moves = self.env['account.move'].search(
            [
                ('date', '>=', date_start),
                ('date', '<=', date_end),
                ('state', '=', 'posted'),
                ('move_type', '=', 'entry'),
                ('line_ids.partner_id', 'in', self.env['res.partner'].search(m_partner_domain).ids)
            ]
        ).filtered(lambda m: m.has_reconciled_entries)
        # Obtener facturas relacionadas a pagos y asientos de pagos
        invoice_ids_from_moves = []
        for move in moves:
            for line in move.line_ids:
                # Revisar si la línea tiene pagos conciliados
                matched_lines = line.matched_debit_ids | line.matched_credit_ids
                for matched in matched_lines:
                    debit_move = matched.debit_move_id.move_id
                    credit_move = matched.credit_move_id.move_id
                    # Si el asiento es de factura
                    if debit_move.move_type in ('out_invoice', 'in_invoice') and 'RC' not in debit_move.name:
                        invoice_ids_from_moves.append(debit_move.id)
                    elif credit_move.move_type in ('out_invoice', 'in_invoice') and 'RC' not in credit_move.name:
                        invoice_ids_from_moves.append(credit_move.id)
                    """
                    reconciled_line = matched.debit_move_id if matched.debit_move_id.move_id.move_type in ('out_invoice','in_invoice') else matched.credit_move_id
                    # Asegurarse que la línea pertenece a una factura
                    if reconciled_line.move_id.move_type in ('out_invoice','in_invoice', 'entry') and 'RC' not in reconciled_line.move_id.name:
                        invoice_ids_from_moves.append(reconciled_line.move_id.id)
                    """
        invoices_from_moves = self.env['account.move'].browse(list(set(invoice_ids_from_moves)))
        # Unir todas las facturas
        invoice_ids = list(set(invoices_from_moves.ids))
        invoices = self.env['account.move'].browse(invoice_ids)
        invoices = invoices.filtered(_has_serial_number)
        total_partners = self._total_payments_by_partner(invoices_from_moves)
        # Filtrar facturas solo de clientes que superen el valor definido
        sales_amount_threshold = self.env.company.sales_amount_report_uafe or 0.0
        if sales_amount_threshold > 0.0:
            partners_over_limit = {partner_id:data for partner_id, data in total_partners.items() if data['total'] > sales_amount_threshold}
            invoices = invoices.filtered(lambda inv: inv.partner_id.id in partners_over_limit)
            # Reasignar total_partners solo con los que cumplen
            total_partners = partners_over_limit
        return {
            'invoices': invoices,
            'payments_by_partner': total_partners,
        }
        
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
        v = remove_accents(value).lower()
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
        return self.env.ref('l10n_ec_reports_penta.action_generate_reports_xlsx').report_action(self)
    
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
        # Mapear datos necesarios para el reporte
        year = int(self.year)
        month = int(self.month)
        last_day = calendar.monthrange(year, month)[1]
        datas = self._get_data_for_reports(date(year, month, 1), date(year, month, last_day), self.domain_uafe)
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            report_files = {
                'DETALLECLIENTE.xlsx': self._generate_detalle_cliente(datas),
                'DETALLEOPERACION.xlsx': self._generate_detalle_operacion(datas),
                'DETALLETRANSACCION.xlsx': self._generate_detalle_transaccion(datas),
                'CABECERA.xlsx': self._generate_cabecera(datas),
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
    
    def _generate_detalle_cliente(self, datas):
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
        # Mapear clientes y valores facturados
        for invoice in datas['invoices']:
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
            worksheet.write(row, 3, sanitize_text(customer.name) or '')
            worksheet.write(row, 4, sanitize_text(customer.display_name) or '')
            worksheet.write(row, 5, customer.country_id.code or '')
            worksheet.write(row, 6, sanitize_text(customer.street) or '')
            worksheet.write(row, 7, state)
            worksheet.write(row, 8, f"{state}{city}" if state and city else '')
            worksheet.write(row, 9, f"{state}{city}{parish}" if state and city and parish else '')
            worksheet.write(row, 10, customer.industry_id and customer.industry_id.code or '')
            worksheet.write(row, 11, int(invoiced_data.get(customer.id, 0.0)) or 0)
        workbook.close()
        output.seek(0)
        return output.read()
    
    def _generate_detalle_operacion(self, datas):
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
        worksheet.set_column('H:H', 20)
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
        operation_count = 0
        for invoice in datas['invoices']:
            customer = invoice.partner_id
            state =  str(customer.state_id.code).zfill(2) if customer.state_id and customer.state_id.code else ''
            city = str(customer.city_id.code).zfill(2) if customer.city_id and customer.city_id.code else ''
            parish = str(customer.parroquia_id.code).zfill(2) if customer.parroquia_id and customer.parroquia_id.code else ''
            count_line = 1
            for line in invoice.invoice_line_ids:
                unit_price = line.price_total / line.quantity if line.quantity else 0
                quantity = int(line.quantity)
                partial_total = 0  # Para controlar el total acumulado
                # Si es rastreable por numeros de serie
                serial_numbers = self.env['stock.lot']
                if line.product_id.is_storable and line.product_id.tracking in ('serial', 'lot'):
                    serial_numbers = invoice.stock_lot_ids.filtered(lambda l, product=line.product_id: l.product_id == product)
                for i in range(quantity):
                    if i == quantity - 1:
                        price = round(line.price_total - partial_total, 2)
                    else:
                        price = round(unit_price, 2)
                        partial_total += price
                    serial_number = serial_numbers[i].name if i < len(serial_numbers) else ''
                    row = worksheet.dim_rowmax + 1
                    worksheet.write(row, 0, self._get_identification_type(invoice.partner_id.l10n_latam_identification_type_id.name) or '')
                    worksheet.write(row, 1, invoice.partner_id.vat or '')
                    if len(invoice.invoice_line_ids) > 1:
                        inv_name = sanitize_text(invoice.name + str(count_line)) or ''
                    else:
                        inv_name = sanitize_text(invoice.name) or ''
                    worksheet.write(row, 2, inv_name)
                    worksheet.write(row, 3, 'VEN')
                    worksheet.write(row, 4, 'NAP')
                    worksheet.write(row, 5, '0')
                    worksheet.write(row, 6, '0')
                    worksheet.write(row, 7, int(price) or 0)
                    self.total_operaciones += int(price) or 0
                    format_date = invoice.invoice_date.strftime('%Y%m%d') if invoice.invoice_date else ''
                    worksheet.write(row, 8, format_date)
                    # Mapear datos vacios
                    worksheet.write(row, 9, '')
                    worksheet.write(row, 10, '')
                    worksheet.write(row, 11, '')
                    worksheet.write(row, 12, sanitize_text(line.product_id.product_brand_id.name) if line.product_id.product_brand_id else '')
                    # CHASIS - N LOTE
                    worksheet.write(row, 13, serial_number)
                    worksheet.write(row, 14, '')
                    worksheet.write(row, 15, 'NO')
                    worksheet.write(row, 16, 'N')
                    worksheet.write(row, 17, 'NO APLICA')
                    # Atributos del producto
                    for atrib in line.product_id.product_template_attribute_value_ids:
                        if atrib.attribute_id.name == 'Año':
                            worksheet.write(row, 9, sanitize_text(atrib.name) or '')
                        elif atrib.attribute_id.name == 'Modelo Homologado ANT':
                            worksheet.write(row, 11, sanitize_text(atrib.name) or '')
                        elif atrib.attribute_id.name == 'Cilindraje':
                            worksheet.write(row, 14, sanitize_text(atrib.name) or '')
                    worksheet.write(row, 18, state)
                    worksheet.write(row, 19, f"{state}{city}" if state and city else '')
                    worksheet.write(row, 20, f"{state}{city}{parish}" if state and city and parish else '')
                    operation_count += 1
                    count_line += 1
        self.total_reg_operaciones = operation_count
        workbook.close()
        output.seek(0)
        return output.read()
    
    def _generate_detalle_transaccion(self, datas):
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
        year = int(self.year)
        month = int(self.month)
        last_day = calendar.monthrange(year, month)[1]
        # Mapear pagos de facturas
        transaction_count = 0
        for invoice in datas['invoices']:
            move_payments = []
            total_payment_amount = 0.0
            # mapear pagos directos
            result = invoice.open_payments()
            retentions = self._get_retentions_data(invoice)
            payment_id = result.get('res_id', False)
            if isinstance(payment_id, int) and payment_id > 0:
                pay = self.env['account.payment'].browse(payment_id)
                move_payments.append(pay.move_id)
            # mapear pagos de asientos POS
            if invoice.invoice_payments_widget and invoice.invoice_payments_widget['content']:
                for pays in invoice.invoice_payments_widget['content']:
                    move_payments.append(pays['move_id'])
            processed_moves = set()
            list_payments = []
            for move_payment in move_payments:
                # Asegurarnos de tener un ID
                if hasattr(move_payment, 'id'):
                    move_payment = move_payment.id
                # Evitar duplicados
                if move_payment in processed_moves:
                    continue
                processed_moves.add(move_payment)
                payment = self.env['account.move'].browse(move_payment)
                # Validar fechas de reporte
                if payment.date >= date(year, month, 1) and payment.date <= date(year, month, last_day):
                    list_payments.append(payment)
                    # Validar que no sea una retencion
                    if payment.id not in retentions.ids:
                        for line in payment.line_ids:
                            # Comporbamos si la línea está reconciliada
                            if line.reconciled:
                                # Obtenemos los matched lines
                                for rec_line in line.matched_debit_ids + line.matched_credit_ids:
                                    # Verificamos si la factura está relacionada (DEBITO)
                                    if rec_line.debit_move_id.move_id.id == invoice.id:
                                        # Obtenemos el numero de conciliación
                                        matching_number = line.matching_number
                                        # Buscamos las líneas de conciliación relacionadas al numero de conciliación y al pago
                                        c_lines = self.env['account.move.line'].search([
                                            ('move_id', '=', payment.id),
                                            ('matching_number', '=', matching_number)
                                        ])
                                        # Sumamos los valores de las líneas de crédito
                                        c_total_lines = sum(c_lines.mapped('credit'))
                                        if rec_line.amount < c_total_lines:
                                            c_total_lines = rec_line.amount
                                        total_payment_amount += c_total_lines
                                    # Verificamos si la factura está relacionada (CREDITO)
                                    if rec_line.credit_move_id.move_id.id == invoice.id:
                                        # Obtenemos el numero de conciliación
                                        matching_number = line.matching_number
                                        # Buscamos las líneas de conciliación relacionadas al numero de conciliación y al pago
                                        d_lines = self.env['account.move.line'].search([
                                            ('move_id', '=', payment.id),
                                            ('matching_number', '=', matching_number)
                                        ])
                                        matching_number = line.matching_number
                                        # Sumamos los valores de las líneas de debito
                                        d_total_lines = sum(d_lines.mapped('debit'))
                                        if rec_line.amount < c_total_lines:
                                            d_total_lines = rec_line.amount
                                        total_payment_amount += d_total_lines
            total_invoice_lines = 0
            for line in invoice.invoice_line_ids:
                if line.quantity > 1:
                    total_invoice_lines += line.quantity
                else:
                    total_invoice_lines += 1
            payment_amount = int(total_payment_amount / total_invoice_lines) if total_invoice_lines > 0 else 0
            count_line = 1
            remaining_payments = list_payments.copy()
            reuse_counter = 0
            for line in invoice.invoice_line_ids:
                quantity = int(line.quantity)
                for i in range(quantity):
                    row = worksheet.dim_rowmax + 1
                    worksheet.write(row, 0, self._get_identification_type(invoice.partner_id.l10n_latam_identification_type_id.name) or '')
                    worksheet.write(row, 1, invoice.partner_id.vat or '')
                    if len(invoice.invoice_line_ids) > 1:
                        inv_name = sanitize_text(invoice.name + str(count_line)) or ''
                    else:
                        inv_name = sanitize_text(invoice.name) or ''
                    worksheet.write(row, 2, inv_name)
                    worksheet.write(row, 3, invoice.date.strftime('%d/%m/%Y') if invoice.date else '')
                    if remaining_payments:
                        payment = remaining_payments.pop(0)
                    else:
                        payment = list_payments[-1] # si se acabaron los pagos, usar el último
                        reuse_counter += 1
                    # aqui consumir un pago de la variable list_payments
                    if reuse_counter > 0:
                        worksheet.write(row, 4, sanitize_text(payment.name + str(reuse_counter)) or '')
                    else:
                        worksheet.write(row, 4, sanitize_text(payment.name) or '')
                    worksheet.write(row, 5, '192')
                    # cliente
                    if invoice.move_type in ('out_invoice', 'out_refund'):
                        self.total_creditos += payment_amount
                    # proveedor
                    else:
                        self.total_debitos += payment_amount
                    worksheet.write(row, 6, payment_amount if invoice.move_type not in ('out_invoice', 'out_refund') else 0)
                    worksheet.write(row, 7, payment_amount if invoice.move_type in ('out_invoice', 'out_refund') else 0)
                    worksheet.write(row, 8, '0')
                    worksheet.write(row, 9, '0')
                    worksheet.write(row, 10, '0')
                    # Cambiar o aplicar logica cuando tengamos definidos los pagos por diario
                    """
                    if payment.journal_id.type == 'cash':
                        worksheet.write(row, 8, payment_amount)
                        self.total_efectivo += payment_amount
                    elif payment.journal_id.type == 'bank':
                        worksheet.write(row, 9, payment_amount)
                        self.total_cheque += payment_amount
                    elif payment.journal_id.type == 'credit':
                        worksheet.write(row, 10, payment_amount)
                        self.total_tarjeta += payment_amount
                    """
                    retention_total = 0
                    # Retenciones
                    for retention in retentions:
                        if retention.date >= date(year, month, 1) and retention.date <= date(year, month, last_day):
                            for line in retention.l10n_ec_withhold_line_ids:
                                for tax in line.tax_ids:
                                    if tax.amount_type == 'percent':
                                        retention_total += line.l10n_ec_withhold_tax_amount
                    self.total_valores_bienes += retention_total
                    self.total_valor_total += int(payment_amount) + int(retention_total)
                    worksheet.write(row, 11, int(retention_total))
                    worksheet.write(row, 12, int(payment_amount) + int(retention_total))
                    worksheet.write(row, 13, sanitize_text(payment.currency_id.name))
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
                    count_line += 1
        self.total_reg_transacciones = transaction_count
        workbook.close()
        output.seek(0)
        return output.read()
    
    def _generate_cabecera(self, datas):
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
        worksheet.write(1, 3, sanitize_text(self.env.user.login) or '')
        worksheet.write(1, 4, self.total_reg_clientes)
        worksheet.write(1, 5, self.total_reg_operaciones)
        worksheet.write(1, 6, self.total_reg_transacciones)
        worksheet.write(1, 7, self.total_operaciones)
        worksheet.write(1, 8, self.total_debitos)
        worksheet.write(1, 9, self.total_creditos)
        worksheet.write(1, 10, self.total_efectivo)
        worksheet.write(1, 11, self.total_cheque)
        worksheet.write(1, 12, self.total_tarjeta)
        worksheet.write(1, 13, self.total_valores_bienes)
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
        return self.env.ref('l10n_ec_reports_penta.action_report_ventas_a1_xlsx').report_action(self)