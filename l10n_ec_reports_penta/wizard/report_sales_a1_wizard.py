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
            ('journal_id.type', '=', 'sale'),
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
        row = 0
        # Encabezados
        headers = ['#', 'TIPO DE COMPROBANTE', 'TIPO DE IDENTIFICACION', 'IDENTIFICACION', 'RAZON SOCIAL', 'PARTE RELACIONADA', 'TIPO DE SUJETO', 'NRO DE DOCUMENTO',
                    'NRO AUTORIZACION', 'FCHA EMISI.']
        # Obtener grupos de impuestos para el reporte
        tax_groups = self.env['account.tax.group'].search([('show_report_a1', '=', True)], order="report_a1_name")
        tax_col = 10
        tax_struct = {}
        # Mapear bases
        for tax_group in tax_groups:
            headers.append('BASE ' + tax_group.report_a1_name.upper())
            tax_struct[tax_group.id] = {'base': tax_col}
            tax_col += 1
        # Mapear ivastax_col
        for tax_group in tax_groups:
            headers.append('MONTO ' + tax_group.report_a1_name.upper())
            tax_struct[tax_group.id]['iva'] = tax_col
            tax_col += 1
        # LLenar el resto del texto de la cabecera
        headers += ['MONTO ICE', 'TOTAL VENTA', 'RET. IVA', 'RET. FUENTE', 'CASILLA 104', 'CASILLA 104 RETENCION', 'DIAS CREDT', 'FORMA PAGO1']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, bold_center)
        # Obtener impuestos a revisar
        #taxs = self.env['account.tax'].search([('tax_group_id', 'in', tax_groups.ids),('type_tax_use', '=', 'sale'),('active', '=', True)], order='amount asc')
        # Mapear datos
        cont = 1
        for invoice in invoices:
            row += 1
            worksheet.write(row, 0, cont, center)
            worksheet.write(row, 1, invoice.l10n_latam_document_type_id.name, center)
            worksheet.write(row, 2, invoice.partner_id.l10n_latam_identification_type_id.name or '', center)
            worksheet.write(row, 3, invoice.partner_id.vat or '', border)
            worksheet.write(row, 4, invoice.partner_id.complete_name or '', border)
            worksheet.write(row, 5, 'SI' if invoice.partner_id.l10n_ec_related_party else 'NO', border)
            subjet_type = ''
            if invoice.partner_id.company_type == 'person':
                subjet_type = 'Persona Natural'
            elif invoice.partner_id.company_type == 'company':
                subjet_type = 'Empresa'
            worksheet.write(row, 6, subjet_type, border)
            worksheet.write(row, 7, invoice.name or '', border)
            worksheet.write(row, 8, invoice.l10n_ec_authorization_number or '', border)
            worksheet.write(row, 9, invoice.invoice_date.strftime("%d/%m/%Y") or '', border)
            # Mapear impuestos BASE
            for tax_group in tax_groups:
                base_amount = 0.0
                iva_amount = 0.0
                for line in invoice.invoice_line_ids:
                    for l_tax in line.tax_ids:
                        if l_tax.tax_group_id == tax_group:
                            base_amount += line.price_subtotal
                            iva_amount  += line.price_subtotal * (l_tax.amount / 100.0)
                if base_amount > 0.00:
                    worksheet.write(row, tax_struct[tax_group.id]['base'], base_amount or 0.00, number)
                    worksheet.write(row, tax_struct[tax_group.id]['iva'], iva_amount or 0.00, number)
                else:
                    worksheet.write(row, tax_struct[tax_group.id]['base'], 0.00, number)
                    worksheet.write(row, tax_struct[tax_group.id]['iva'], 0.00, number)
            # Monto ICE
            worksheet.write(row, tax_col, 0.00, number)
            worksheet.write(row, tax_col+1, invoice.amount_total, number)
            worksheet.write(row, tax_col+2, 0.00, number)
            worksheet.write(row, tax_col+3, 0.00, number)
            # Casilla 104
            all_tags = invoice.invoice_line_ids.mapped("tax_tag_ids.name")
            all_tags = list(set(all_tags))
            worksheet.write(row, tax_col+4, all_tags[0] if all_tags else '', border)
            # Casilla Retenciones
            if invoice.l10n_ec_withhold_ids:
                all_tags = invoice.l10n_ec_withhold_ids.filtered(lambda w: w.state == "posted").line_ids.mapped("tax_tag_ids.name")
                all_tags = list(set(all_tags))
                worksheet.write(row, tax_col+5, all_tags[0] if all_tags else '', border)
            else:
                worksheet.write(row, tax_col+5, '', border)
            worksheet.write(row, tax_col+6, invoice.invoice_payment_term_id.name if invoice.invoice_payment_term_id else '', border)
            worksheet.write(row, tax_col+7, invoice.l10n_ec_sri_payment_id.name if invoice.l10n_ec_sri_payment_id else '', border)
            cont += 1
        workbook.close()
        output.seek(0)
        return output.read()