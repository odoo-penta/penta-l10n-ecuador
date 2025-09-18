# -*- coding: utf-8 -*-
from odoo import models, fields
import base64
import io
from odoo.tools.misc import xlsxwriter
from odoo.addons.penta_base.reports.xlsx_formats import get_xlsx_formats


class ReportRetentionsA3Wizard(models.TransientModel):
    _name = 'report.retentions.a3.wizard'
    _description = 'Wizard to generate report retentions A3'
    
    date_start = fields.Date(string='Desde', required=True)
    date_end = fields.Date(string='Hasta', required=True)
    retention_type = fields.Selection([
        ('all', 'Todos'),
        ('vat_withholding', 'Retencion IVA'),
        ('income_withholding', 'Retencion Fuente')
        ], string='Tipo de Retención', required=True, default='all')
    apply_percentage_filter = fields.Boolean(string='Aplicar filtro de porcentaje')
    percentage_operator = fields.Selection([
        ('=', 'Igual a'),
        ('>=', 'Mayor o igual'),
        ('<=', 'Menor o igual'),
        ('>', 'Mayor que'),
        ('<', 'Menor que'),
    ], string='Operador porcentaje', default='=')
    percentage_value = fields.Float(string='Valor porcentaje')
    
    def print_report(self):
        report = self.generate_xlsx_report()
        today = fields.Date.context_today(self)
        file_name = f"RetencionesComprasA3_{today.strftime('%d_%m_%Y')}.xlsx"
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': base64.b64encode(report),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
        
    def _get_moves_data(self):
        # Generar data para reporte
        move_domain = [
            ('state', '=', 'posted'),
            ('date', '>=', self.date_start),
            ('date', '<=', self.date_end),
            ('journal_id.l10n_ec_withhold_type', '=', 'in_withhold'),
        ]
        moves = self.env['account.move'].search(move_domain, order='date asc')
        return moves
    
    def _compare_percent(self, percent):
        op = self.percentage_operator
        val = self.percentage_value
        if op == '=':
            return percent == val
        elif op == '>=':
            return percent >= val
        elif op == '<=':
            return percent <= val
        elif op == '>':
            return percent > val
        elif op == '<':
            return percent < val
        return True
    
    def generate_xlsx_report(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Retenciones compras")
        # Formatos
        formats = get_xlsx_formats(workbook)
        # Obtener data
        moves = self._get_moves_data()
        iva_tax_groups = self.env['account.tax.group'].search([('type_ret', 'in', ['withholding_iva_purchase', 'withholding_iva_purchase'])])
        rent_tax_groups = self.env['account.tax.group'].search([('type_ret', 'in', ['withholding_rent_purchase', 'withholding_rent_purchase'])])
        # Ancho de columnas
        worksheet.set_column('A:A', 6)
        worksheet.set_column('B:C', 24)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 30)
        worksheet.set_column('F:G', 20)
        worksheet.set_column('H:I', 22)
        worksheet.set_column('J:J', 15)
        # Encabezados
        headers = ['#', 'FECHA DE EMISIÓN', 'DIARIO', 'NÚMERO DE RETENCIÓN', 'RUC', 'RAZÓN SOCIAL', 'AUTORIZACIÓN SRI', 'BASE IMPONIBLE', 'VALOR RETENIDO',
                   'PORCENTAJE DE RETENCIÓN', 'CÓDIGO BASE', 'CÓDIGO APLICADO', 'CÓDIGO ATS', 'NRO DE DOCUMENTO', 'FECHA EMISIÓN FACTURA PROVEEDOR',
                   'CUENTA CONTABLE']
        # Mapear cabecera
        company_name = self.env.company.display_name
        worksheet.merge_range('A1:E1', company_name)
        date_from = self.date_start
        worksheet.merge_range('A2:B2', 'Fecha Desde:')
        worksheet.write('C2', date_from.strftime('%d/%m/%Y') if date_from else '')
        date_to = self.date_end
        worksheet.merge_range('A3:B3', 'Fecha Hasta:')
        worksheet.write('C3', date_to.strftime('%d/%m/%Y') if date_to else '')
        worksheet.merge_range('A4:B4', 'Reporte:')
        worksheet.write('C4', 'RETENCIONES COMPRAS A3')
        row = 5
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, formats['header_bg'])
        # Mapear datos
        row += 1
        cont = 1
        for move in moves:
            invoice = move.line_ids.mapped('l10n_ec_withhold_invoice_id').id
            if invoice:
                invoice = self.env['account.move'].browse(invoice)
                for reten in move.l10n_ec_withhold_line_ids:
                    # Aplicar filtro de tipo de retencion
                    is_vat = reten.tax_ids.tax_group_id.id in iva_tax_groups.ids
                    is_income = reten.tax_ids.tax_group_id.id in rent_tax_groups.ids
                    if self.retention_type == 'vat_withholding' and not is_vat:
                        continue
                    if self.retention_type == 'income_withholding' and not is_income:
                        continue
                    # Aplicar filtro de porcentaje si corresponde
                    percent = abs(reten.tax_ids.amount)
                    if self.apply_percentage_filter:
                        if not self._compare_percent(percent):
                            continue
                    worksheet.write(row, 0, cont, formats['center'])
                    worksheet.write(row, 1, move.date.strftime("%d/%m/%Y") or '', formats['border'])
                    worksheet.write(row, 2, move.journal_id.name, formats['center'])
                    worksheet.write(row, 3, move.name, formats['center'])
                    worksheet.write(row, 4, move.partner_id.vat or '', formats['border'])
                    worksheet.write(row, 5, move.partner_id.complete_name or '', formats['border'])
                    worksheet.write(row, 6, move.l10n_ec_authorization_number or '', formats['border'])
                    worksheet.write(row, 7, reten.balance or '', formats['currency'])
                    worksheet.write(row, 8, reten.l10n_ec_withhold_tax_amount or 0.00, formats['currency'])
                    # Obtener porcentaje de retencion
                    worksheet.write(row, 9, (percent/100) or 0.00, formats['percent'])
                    # Obtener codigos de retencion
                    worksheet.write(row, 10, reten.tax_tag_ids.name or '', formats['center'])
                    worksheet.write(row, 11, reten.tax_ids.name or '', formats['center'])
                    worksheet.write(row, 12, reten.tax_ids.l10n_ec_code_ats or '', formats['center'])
                    # Numero de documento
                    worksheet.write(row, 13, invoice.name or '', formats['center'])
                    worksheet.write(row, 14, invoice.date.strftime("%d/%m/%Y") or '', formats['border'])
                    # Obtener cuenta contable
                    account_name = ''
                    for line in move.line_ids:
                        if line.tax_line_id == reten.tax_ids:
                            account_name = line.account_id.code + ' ' + line.account_id.name
                            break
                    worksheet.write(row, 15, account_name, formats['center'])
                    row += 1
                    cont += 1
        workbook.close()
        output.seek(0)
        return output.read()