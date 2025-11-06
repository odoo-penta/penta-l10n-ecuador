from odoo import models, fields
import base64
import io
import math
from odoo.tools.misc import xlsxwriter

class ReportPurchaseRetentionsWizard(models.TransientModel):
    _name = 'report.purchase.retentions.wizard'
    _description = 'Wizard to generate report purchase and retentions'

    date_start = fields.Date(string='Date start')
    date_end = fields.Date(string='Date end')
    
    def _get_invoices_data(self):
        # Generar data para reporte
        invoices = self.env['account.move'].search([
            ('state', '=', 'posted'),
            ('invoice_date', '>=', self.date_start),
            ('invoice_date', '<=', self.date_end),
            ('move_type', '=', 'in_invoice')
            ], order='invoice_date asc')
        return invoices
    
    def _get_retentions_data(self, invoice):
        # Obtener datos de retenciones de la factura
        data = invoice.l10n_ec_action_view_withholds()
        move_obj = self.env['account.move']
        if data and data['res_id']:
            retentions = move_obj.browse(data['res_id'])
        else:
            retentions = move_obj
        return retentions
    
    def print_report(self):
        report = self.generate_xlsx_report()
        attachment = self.env['ir.attachment'].create({
            'name': 'ComprasRetenciones.xlsx',
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
        worksheet = workbook.add_worksheet("ComprasRetenciones")
        # Formatos
        bold_center = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        bold = workbook.add_format({'bold': True, 'border': 1})
        border = workbook.add_format({'border': 1})
        center = workbook.add_format({'align': 'center', 'border': 1})
        number = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        title_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        # Obtener data
        invoices = self._get_invoices_data()
        # Reporte compras y retenciones
        # Ancho de columnas
        worksheet.set_column('A:A', 6)
        worksheet.set_column('B:B', 12)
        worksheet.set_column('C:C', 16)
        worksheet.set_column('D:D', 30)
        worksheet.set_column('E:E', 20)
        worksheet.set_column('F:F', 35)
        worksheet.set_column('G:J', 12)
        worksheet.set_column('K:K', 15)
        worksheet.set_column('T:U', 20)
        # Titulo
        worksheet.merge_range('A1:K1', 'REPORTE DE COMPRAS', title_format)
        worksheet.merge_range('L1:P1', 'RETENCIONES RENTA', title_format)
        worksheet.merge_range('Q1:S1', 'RETENCIONES IVA', title_format)
        worksheet.merge_range('T1:T2', 'VALOR A PAGAR', title_format)
        worksheet.merge_range('U1:U2', 'NÚMERO RETENCIÓN', title_format)
        row = 1
        # Subtitulo
        worksheet.write(row, 0, 'CANT', bold_center)
        worksheet.write(row, 1, 'FECHA', bold_center)
        worksheet.write(row, 2, 'RUC', bold_center)
        worksheet.write(row, 3, 'PROVEEDOR', bold_center)
        worksheet.write(row, 4, 'NO. FACTURA', bold_center)
        worksheet.write(row, 5, 'DESCRIPCION', bold_center)
        worksheet.write(row, 6, 'VALOR 0%', bold_center)
        worksheet.write(row, 7, 'VALOR 15%', bold_center)
        worksheet.write(row, 8, 'RIMPE', bold_center)
        worksheet.write(row, 9, 'IVA', bold_center)
        worksheet.write(row, 10, 'TOTAL', bold_center)
        worksheet.write(row, 11, '1,75%', bold_center)
        worksheet.write(row, 12, '2,75%', bold_center)
        worksheet.write(row, 13, '1%', bold_center)
        worksheet.write(row, 14, '10%', bold_center)
        worksheet.write(row, 15, '0%', bold_center)
        worksheet.write(row, 16, '30%', bold_center)
        worksheet.write(row, 17, '70%', bold_center)
        worksheet.write(row, 18, '100%', bold_center)
        cont = 1
        # Mapear datos
        for invoice in invoices:
            row += 1
            worksheet.write(row, 0, cont, center)
            worksheet.write(row, 1, invoice.invoice_date.strftime('%d/%m/%Y') if invoice.date else '', center)
            worksheet.write(row, 2, invoice.partner_id.vat or '', center)
            worksheet.write(row, 3, invoice.partner_id.name or '', border)
            worksheet.write(row, 4, invoice.name or '', border)
            worksheet.write(row, 5, invoice.ref or '', border)
            # Valores
            if math.isclose(invoice.amount_tax, 0.0, abs_tol=1e-9):
                worksheet.write(row, 6, invoice.amount_untaxed, border)
                worksheet.write(row, 7, 0.00, number)
            else:
                worksheet.write(row, 6, 0.00, border)
                worksheet.write(row, 7, invoice.amount_untaxed, number)
            worksheet.write(row, 8, '', border)
            worksheet.write(row, 9, invoice.amount_tax, number)
            worksheet.write(row, 10, invoice.amount_total, number)
            # Mapeo de porcentaje a columna
            amount_to_col = {
                -1.75: 11,
                -2.75: 12,
                -1:    13,
                -10:   14,
                -0:    15,
                -30:   16,
                -70:   17,
                -100:  18,
            }
            # Inicializar todas las columnas con 0.0
            for col in amount_to_col.values():
                worksheet.write(row, col, 0.0, number)
            # Retenciones
            retention_names = []
            retentions = self._get_retentions_data(invoice)
            for retention in retentions:
                retention_names.append(retention.name or '')
                for line in retention.l10n_ec_withhold_line_ids:
                    for tax in line.tax_ids:
                        if tax.amount_type == 'percent':
                            col = amount_to_col.get(tax.amount)
                            if col:
                                worksheet.write(row, col, line.l10n_ec_withhold_tax_amount or 0.0, number)
            # Generar texto de retenciones
            if retention_names:
                retention_txt = ', '.join([f"{name}" for name in retention_names if name])
            else:
                retention_txt = ''
            # Total a pagar (TOTAL - SUMA DE RETENCIONES RENTA)
            formula = f"K{row+1}-SUM(L{row+1}:S{row+1})"
            worksheet.write_formula(row, 19, formula, number)
            # Texto retenciones
            worksheet.write(row, 20, retention_txt, border)
            cont += 1
        # Totales por columna
        row += 1
        worksheet.write(row, 5, 'TOTALES', bold)
        worksheet.write_formula(row, 6, f"SUM(G3:G{row})", bold_center)
        worksheet.write_formula(row, 7, f"SUM(H3:H{row})", bold_center)
        worksheet.write_formula(row, 8, f"SUM(I3:I{row})", bold_center)
        worksheet.write_formula(row, 9, f"SUM(J3:J{row})", bold_center)
        worksheet.write_formula(row, 10, f"SUM(K3:K{row})", bold_center)
        worksheet.write_formula(row, 11, f"SUM(L3:L{row})", bold_center)
        worksheet.write_formula(row, 12, f"SUM(M3:M{row})", bold_center)
        worksheet.write_formula(row, 13, f"SUM(N3:N{row})", bold_center)
        worksheet.write_formula(row, 14, f"SUM(O3:O{row})", bold_center)
        worksheet.write_formula(row, 15, f"SUM(P3:P{row})", bold_center)
        worksheet.write_formula(row, 16, f"SUM(Q3:Q{row})", bold_center)
        worksheet.write_formula(row, 17, f"SUM(R3:R{row})", bold_center)
        worksheet.write_formula(row, 18, f"SUM(S3:S{row})", bold_center)
        worksheet.write_formula(row, 19, f"SUM(T3:T{row})", bold_center)
        workbook.close()
        output.seek(0)
        return output.read()
