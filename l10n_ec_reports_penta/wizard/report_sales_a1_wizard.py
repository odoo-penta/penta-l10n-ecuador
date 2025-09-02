from odoo import models, fields
from datetime import datetime, date
import calendar
import zipfile
import base64
import io
from collections import defaultdict
from odoo.tools.misc import xlsxwriter
from odoo.tools import remove_accents, sanitize_text, extract_numbers

class ReportSalesA1Wizard(models.TransientModel):
    _name = 'report.sales.a1.wizard'
    _description = 'Wizard to generate report sales A1'

    def _get_selection_opcions(self):
        options = [('0', 'Todos')]
        types = self.env['l10n_latam.document.type'].search([('active', '=', True)])
        for t in types:
            options.append((str(t.id), t.name))
        return options
    
    date_start = fields.Date(string='Date start', required=True)
    date_end = fields.Date(string='Date end', required=True)
    document_type = fields.Selection(selection=lambda self: self._get_selection_opcions(), default='0', required=True)
    
    def _get_invoices_data(self):
        # Generar data para reporte
        inv_domain = [
            ('state', '=', 'posted'),
            ('invoice_date', '>=', self.date_start),
            ('invoice_date', '<=', self.date_end),
        ]
        if self.document_type != '0':
            inv_domain.append(('l10n_latam_document_type_id', '=', int(self.document_type)))
        invoices = self.env['account.move'].search(inv_domain, order='invoice_date asc')
        return invoices
    
    def print_report(self):
        report = self.generate_xlsx_report()
        attachment = self.env['ir.attachment'].create({
            'name': 'Ventas A1.xlsx',
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
    
    def generate_xlsx_report(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Ventas A1")
        # Formatos
        bold_center = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        bold = workbook.add_format({'bold': True, 'border': 1})
        border = workbook.add_format({'border': 1})
        center = workbook.add_format({'align': 'center', 'border': 1})
        number = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        title_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        # Obtener data
        invoices = self._get_invoices_data()
        # Ancho de columnas
        worksheet.set_column('A:A', 6)
        worksheet.set_column('B:C', 24)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 30)
        worksheet.set_column('F:G', 20)
        worksheet.set_column('H:I', 22)
        worksheet.set_column('J:J', 15)
        worksheet.set_column('N:N', 25)
        worksheet.set_column('O:T', 15)
        worksheet.set_column('V:X', 15)
        worksheet.set_column('Y:Y', 30)
        row = 0
        # Encabezados
        headers = ['#', 'TIPO DE COMPROBANTE', 'TIPO DE IDENTIFICACION', 'IDENTIFICACION', 'RAZON SOCIAL', 'PARTE RELACIONADA', 'TIPO DE SUJETO', 'NRO DE DOCUMENTO',
                    'NRO AUTORIZACION', 'FCHA EMISI.', 'BASE 0%', 'BASE 5%', 'BASE 15%', 'BASE NO OBJETO DE IVA', 'MONTO IVA 5%', 'MONTO IVA 15%', 'MONTO IVA 8%',
                    'MONTO IVA 15', 'MONTO ICE', 'TOTAL VENTA', 'RET. IVA', 'RET. FUENTE', 'CASILLA 104', 'DIAS CREDT', 'FORMA PAGO1']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, bold_center)
        cont = 1
        # Mapear datos
        for invoice in invoices:
            row += 1
            worksheet.write(row, 0, cont, center)
            worksheet.write(row, 1, invoice.l10n_latam_document_type_id.name, center)
            worksheet.write(row, 2, invoice.partner_id.l10n_latam_identification_type_id.name or '', center)
            worksheet.write(row, 3, invoice.partner_id.vat or '', border)
            worksheet.write(row, 4, invoice.partner_id.complete_name or '', border)
            worksheet.write(row, 5, 'SI' if invoice.partner_id.l10n_ec_related_party else 'NO', border)
            worksheet.write(row, 6, invoice.partner_id.company_type or '', border)
            worksheet.write(row, 7, invoice.name or '', border)
            worksheet.write(row, 8, invoice.l10n_ec_authorization_number or '', border)
            worksheet.write(row, 9, invoice.invoice_date.strftime("%d/%m/%Y") or '', border)
            # Calcular valores con iva 0%, 5% y 15 %
            tax_0_lines = invoice.invoice_line_ids.filtered(
                lambda l: any(t.amount_type == 'percent' and t.amount == 0 and t.l10n_ec_code_base not in (441, 444, 541, 545) for t in l.tax_ids)
            )
            tax_5_lines = invoice.invoice_line_ids.filtered(
                lambda l: any(t.amount_type == 'percent' and t.amount == 5 for t in l.tax_ids)
            )
            tax_15_lines = invoice.invoice_line_ids.filtered(
                lambda l: any(t.amount_type == 'percent' and t.amount == 15 for t in l.tax_ids)
            )
            tax_no_lines = invoice.invoice_line_ids.filtered(
                lambda l: any(t.l10n_ec_code_base in (441, 444, 541, 545) for t in l.tax_ids)
            )
            tax_0_base = sum(tax_0_lines.mapped('price_subtotal'))
            tax_5_base = sum(tax_5_lines.mapped('price_subtotal'))
            tax_15_base = sum(tax_15_lines.mapped('price_subtotal'))
            tax_no_base = sum(tax_no_lines.mapped('price_subtotal'))
            # Montos BASE
            worksheet.write(row, 10, tax_0_base or 0.00, number)
            worksheet.write(row, 11, tax_5_base or 0.00, number)
            worksheet.write(row, 12, tax_15_base or 0.00, number)
            worksheet.write(row, 13, tax_no_base or 0.00, number)
            # Montos IVA
            worksheet.write(row, 14, round(tax_5_base * 0.05, 2) or 0.00, number)
            worksheet.write(row, 15, round(tax_15_base * 0.15, 2), number)
            worksheet.write(row, 16, 0.00, number)
            worksheet.write(row, 17, round(tax_15_base * 0.15, 2), number)
            # Monto ICE
            worksheet.write(row, 18, 0.00, number)
            worksheet.write(row, 19, invoice.amount_total, number)
            worksheet.write(row, 20, 0.00, number)
            worksheet.write(row, 21, 0.00, number)
            # Casilla 104
            all_tags = invoice.invoice_line_ids.mapped("tax_tag_ids.name")
            all_tags = list(set(all_tags))
            worksheet.write(row, 22, all_tags[0] if all_tags else '', border)
            worksheet.write(row, 23, invoice.invoice_payment_term_id.name if invoice.invoice_payment_term_id else '', border)
            worksheet.write(row, 24, invoice.l10n_ec_sri_payment_id.name if invoice.l10n_ec_sri_payment_id else '', border)
            cont += 1
        workbook.close()
        output.seek(0)
        return output.read()