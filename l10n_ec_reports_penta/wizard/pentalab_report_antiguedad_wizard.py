import base64
from io import BytesIO
from odoo import models, fields, api
import xlsxwriter
from collections import defaultdict
from datetime import date, datetime, time
from odoo.exceptions import UserError


ACCOUNT_TYPE_SELECTION = [
    ('asset_receivable', 'Por cobrar'),
]

class PentalabReportAntiguedadWizard(models.TransientModel):
    _name = 'pentalab.report.antiguedad.wizard'
    _description = 'Wizard para Reporte Antigüedad'
    
     # Opción 1: varias cuentas (reemplaza al antiguo account_id)
    account_ids = fields.Many2many(
        'account.account',
        'pentalab_report_ant_wizard_account_rel',
        'wizard_id', 'account_id',
        string='Cuentas contables',
        domain=[('account_type', 'in', ('asset_receivable', 'liability_payable', 'liability_credit_card'))],
        help='Selecciona una o varias cuentas.'
    )
      # Opción 2: por tipo + check comercial (SOLO CHECK, sin impacto en filtros)
    account_type = fields.Selection(
        ACCOUNT_TYPE_SELECTION,
        string='Tipo de cuenta'
    )
    no_commercial_only = fields.Boolean(
        string='NO Comercial',
        help='Marcador informativo. No altera filtros ni resultados.'
    )
    date = fields.Date(
        string='Fecha de corte'
    )
    file_name = fields.Char(string='Nombre del archivo')
    file_data = fields.Binary(string='Archivo', readonly=True)
    
    def _date_str(self,d):
        """Devuelve 'dd-mm-yyyy' o '' si no hay fecha."""
        return d.strftime('%d-%m-%Y') if d else ''

    def _validate_mode(self):
        for w in self:
            if w.account_ids and w.account_type:
                raise UserError("Selecciona EITHER cuentas específicas O un tipo de cuenta, no ambos.")
            if not w.account_ids and not w.account_type:
                raise UserError("Debes seleccionar cuentas específicas o un tipo de cuenta.")

    def action_generate_report(self):
        self.ensure_one()
        # Validación: o cuentas o tipo (excluyentes)
        if self.account_ids and self.account_type:
            raise UserError("Selecciona cuentas específicas O un tipo de cuenta, no ambos.")
        if not self.account_ids and not self.account_type:
            raise UserError("Debes seleccionar cuentas específicas o un tipo de cuenta.")
        if self.account_ids:
            file_tag = 'varias'
        else:
            file_tag = dict(ACCOUNT_TYPE_SELECTION).get(self.account_type, 'tipo')
        cutoff_date = self.date or date.today()
        if self.account_type == 'asset_receivable':
            # Reporte base de antiguedad
            report = self.env.ref('account_reports.aged_receivable_report')
            # Restar 5 anios a la fecha de corte
            date_from = cutoff_date.replace(year=cutoff_date.year - 5, month=1, day=1)
            # Agg fecha de corte en las opciones del reporte
            date_options = {
                'date': {
                    'mode': 'range',
                    'date_from': date_from.strftime('%Y-%m-%d'),
                    'date_to': cutoff_date.strftime('%Y-%m-%d'),
                    'filter': 'custom',
                }
            }
            # Invocamos al reporte para que aplique sus filtros y lógica
            options = report.get_options(previous_options=date_options)
            # Setear compania en el options
            options['companies'] = [
                {
                    'id': c.id,
                    'name': c.name,
                    'currency_id': c.currency_id.id,
                }
                for c in self.env.companies
            ]
            # Option para expandir lineas
            options['unfold_all'] = True
            # Option para mostrar la cuenta contable
            options['show_account'] = True
            # Options de no relaciones
            if self.no_commercial_only:
                for opt in options.get('account_type', []):
                    if opt.get('id') == 'non_trade_receivable':
                        opt['selected'] = True
            # Obtener lineas del reporte y procesar datos
            data_lines = []
            for line in report._get_lines(options):
                aml = self.env['account.move.line']
                aml_line_id = line.get("id")
                if aml_line_id and 'account.move.line' in aml_line_id:
                    aml_id = int(aml_line_id.split("account.move.line~")[1])
                    aml = self.env['account.move.line'].browse(aml_id)
                    cols = [c.get('no_format', c.get('name')) for c in line.get('columns', [])]
                    data_lines.append({
                        'aml': aml,
                        'name': line.get('name'),
                        'columns': cols,
                    })
            # XLSX
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('Movimientos')

            header_format = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1'})
            money_format = workbook.add_format({'num_format': '#,##0.00'})

            headers = [
                'Diario', 'Cuenta', 'Nombre del socio', 'Número de factura',
                'Fecha de factura', 'Fecha de vencimiento', 'Referencia', 'Importe',
                'En fecha', '1-30', '31-60', '61-90', '91-120', 'más de 120'
            ]
            sheet.write(0, 5, 'Al')
            sheet.write(0, 6, self._date_str(cutoff_date))
            for col, title in enumerate(headers):
                sheet.write(1, col, title, header_format)
            row = 2
            for line in data_lines:
                # Obtener datos básicos
                invoice_name_full = line['name']
                invoice_number = invoice_name_full
                parts = invoice_name_full.split()
                if parts and (parts[0] == 'Fact' or parts[0] == 'NotCr') and len(parts) > 1:
                    invoice_number = f"{parts[0]} {parts[1]}"
                else:
                    invoice_number = parts[0] if parts else invoice_name_full
                invoice = self.env['account.move'].search([('name', '=', invoice_number)])
                # Obtener datos básicos
                invoice_name_full = line['name']
                invoice_number = invoice_name_full
                parts = invoice_name_full.split()
                if parts and (parts[0] == 'Fact' or parts[0] == 'NotCr') and len(parts) > 1:
                    invoice_number = f"{parts[0]} {parts[1]}"
                else:
                    invoice_number = parts[0] if parts else invoice_name_full
                invoice_date = line['columns'][0].strftime('%d/%m/%Y') if line['columns'][0] else ''
                importe = next((x for x in line['columns'][1:7] if x), 0.0)
                
                r_line = line['aml']
                account = r_line.account_id if r_line.account_id else self.env['account.account']
                account_name = f"{r_line.account_id.code or ''} {r_line.account_id.name or ''}" if r_line.account_id else ''
                partner_name =  r_line.partner_id.name if r_line.partner_id else ''
                journal_name = r_line.move_id.journal_id.name
                ref = r_line.ref
                
                # Mapear datos a columnas
                sheet.write(row, 0, journal_name) # Diario
                sheet.write(row, 1, account_name) # Cuenta
                sheet.write(row, 2, partner_name) # Nombre del socio
                sheet.write(row, 3, invoice_name_full) # Número de factura
                sheet.write(row, 4, invoice_date) # Fecha de factura
                
                # --- Fechas base ---
                is_cc = (r_line.account_id and r_line.account_id.account_type == 'liability_credit_card')
                fecha_pago = r_line.date
                fecha_prevista_cc = r_line.payment_id.bank_forecast_date if r_line.payment_id else False
                # Para NO CC tomamos la fecha de vencimiento; si no hay, usamos la fecha del documento
                fecha_venc = fecha_prevista_cc if is_cc else (r_line.date_maturity or r_line.date)
                if fecha_venc:
                    sheet.write(row, 5, fecha_venc.strftime('%d-%m-%Y')) # Fecha de vencimiento
                sheet.write(row, 6, ref) # Referencia
                sheet.write_number(row, 7, importe, money_format) # Importe

                # --- Días vencidos según tipo de cuenta ---
                # Usamos la misma fecha_venc definida arriba
                if fecha_venc:
                    due_date = fecha_venc
                    if cutoff_date >= due_date:
                        dias_vencidos = int((cutoff_date - due_date).days) if due_date else 0
                    else:
                        dias_vencidos = 0
                    #dias_vencidos = int((cutoff_date - due_date).days) if due_date else 0
                    if dias_vencidos == 0:
                        sheet.write_number(row, 8, importe, money_format) # En fecha
                    else:
                        if dias_vencidos >= 1 and dias_vencidos <= 30:
                            sheet.write_number(row, 9, importe, money_format)  # 1-30
                        elif dias_vencidos >= 31 and dias_vencidos <= 60:
                            sheet.write_number(row, 10, importe, money_format)  # 31-60
                        elif dias_vencidos >= 61 and dias_vencidos <= 90:
                            sheet.write_number(row, 11, importe, money_format)  # 61-90
                        elif dias_vencidos >= 91 and dias_vencidos <= 120:
                            sheet.write_number(row, 12, importe, money_format)  # 91-120
                        elif dias_vencidos >= 121:
                            sheet.write_number(row, 13, importe, money_format)  # más de 120
                row += 1
        else:
            # Dominio base
            domain = [
                ('move_id.state', '=', 'posted'),
                ('date', '<=', cutoff_date),
            ]

            # Filtro según selección (el check 'commercial_only' NO afecta los filtros)
            if self.account_ids:
                domain.append(('account_id', 'in', self.account_ids.ids))
                file_tag = 'varias'
            else:
                domain.append(('account_id.account_type', '=', self.account_type))
                file_tag = dict(ACCOUNT_TYPE_SELECTION).get(self.account_type, 'tipo')

            lines = self.env['account.move.line'].search(domain, order='date desc')

            # Agrupar balances por matching_number
            matching_balances = defaultdict(float)
            for line in lines:
                if line.matching_number:
                    matching_balances[line.matching_number] += line.debit - line.credit

            # XLSX
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('Movimientos')

            header_format = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1'})
            money_format = workbook.add_format({'num_format': '#,##0.00'})

            headers = [
                'Diario', 'Cuenta', 'Nombre del socio', 'Número de factura',
                'Fecha de factura', 'Fecha de vencimiento', 'Referencia', 'Importe',
                'En fecha', '1-30', '31-60', '61-90', '91-120', 'más de 120'
            ]
            sheet.write(0, 5, 'Al')
            sheet.write(0, 6, self._date_str(cutoff_date))
            for col, title in enumerate(headers):
                sheet.write(1, col, title, header_format)

            row = 2
            for line in lines:
                matching_number = line.matching_number or ''
                importe = line.debit - line.credit
                balance_emparejamiento = matching_balances.get(matching_number, 0.0) if matching_number else 0.0

                mostrar_linea = (
                    not matching_number or  # líneas sin emparejamiento
                    abs(balance_emparejamiento) > 0.0001  # o con balance no cero
                )

                if mostrar_linea:
                    sheet.write(row, 0, line.journal_id.name or '')
                    sheet.write(row, 1, f'{line.account_id.code or ""} {line.account_id.name or ""}')
                    sheet.write(row, 2, line.partner_id.name or '')
                    sheet.write(row, 3, line.move_id.name or '')
                    sheet.write(row, 4, str(line.date or ''))
                    sheet.write(row, 5, str(line.payment_id.bank_forecast_date or ''))
                    sheet.write(row, 6, line.move_id.ref or '')
                    sheet.write(row, 7, importe, money_format)
                    sheet.write(row, 7, importe, money_format)

                    # Solo se llena la columna 8 ("En fecha") si la fecha_corte está entre la fecha del pago y la prevista
                    fecha_pago = line.date
                    fecha_prevista = line.payment_id.bank_forecast_date
                    if fecha_pago and fecha_prevista and fecha_pago <= cutoff_date <= fecha_prevista:
                        sheet.write(row, 8, importe, money_format)
                    else:
                        sheet.write(row, 8, '', money_format)

                    # Cálculo de días vencidos
                    dias_vencidos = (date.today() - line.payment_id.bank_forecast_date).days if line.payment_id.bank_forecast_date else 0
                    dias_vencidos = int(dias_vencidos)
                    
                    # Inicializar columnas de rangos
                    rangos = ['', '', '', '', '']

                    if 1 <= dias_vencidos <= 30:
                        rangos[0] = importe
                    elif 31 <= dias_vencidos <= 60:
                        rangos[1] = importe
                    elif 61 <= dias_vencidos <= 90:
                        rangos[2] = importe
                    elif 91 <= dias_vencidos <= 120:
                        rangos[3] = importe
                    elif dias_vencidos > 120:
                        rangos[4] = importe

                    for i, valor in enumerate(rangos):
                        sheet.write(row, 9 + i, valor, money_format)

                    row += 1

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())

        self.file_name = f'reporte_antiguedad_{file_tag}.xlsx'
        self.file_data = file_data

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/?model={self._name}&id={self.id}&field=file_data&filename_field=file_name&download=true",
            'target': 'new',
        }