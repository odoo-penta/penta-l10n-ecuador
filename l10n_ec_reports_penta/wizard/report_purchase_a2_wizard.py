# -*- coding: utf-8 -*-
from odoo import models, fields
import base64
import io
from odoo.tools.misc import xlsxwriter
from odoo.addons.penta_base.reports.xlsx_formats import get_xlsx_formats


class ReportPurchaseA2Wizard(models.TransientModel):
    _name = 'report.purchase.a2.wizard'
    _description = 'Wizard to generate report sales A1'

    def _get_selection_opcions(self):
        options = [('0', 'Todos')]
        types = self.env['l10n_latam.document.type'].search([('active', '=', True)])
        for t in types:
            options.append((str(t.id), t.name))
        return options
    
    date_start = fields.Date(string='Desde', required=True)
    date_end = fields.Date(string='Hasta', required=True)
    document_type = fields.Selection(selection=lambda self: self._get_selection_opcions(), default='0', string='Tipo documento', required=True)
    
    def _get_invoices_data(self):
        # Generar data para reporte
        inv_domain = [
            ('state', '=', 'posted'),
            ('invoice_date', '>=', self.date_start),
            ('invoice_date', '<=', self.date_end),
            ('journal_id.type', '=', 'purchase'),
            ('journal_id.l10n_latam_use_documents','=', True),
        ]
        if self.document_type != '0':
            inv_domain.append(('l10n_latam_document_type_id', '=', int(self.document_type)))
        invoices = self.env['account.move'].search(inv_domain, order='invoice_date asc')
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
        today = fields.Date.context_today(self)
        file_name = f"ComprasA2_{today.strftime('%d_%m_%Y')}.xlsx"
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
    
    def generate_xlsx_report(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Ventas A1")
        # Formatos
        formats = get_xlsx_formats(workbook)
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
        # Encabezados
        headers = ['#', 'SUSTENTO TRIBUTARIO', 'TIPO DE IDENTIFICACIÓN', 'IDENTIFICACIÓN', 'RAZÓN SOCIAL', 'TIPO DE CONTRIBUYENTE', 'PARTE RELACIONADA', 'TIPO DE SUJETO', 'TIPO DE COMPROBANTE', 'NÚMERO DE FACTURA',
                    'AUTORIZACIÓN', 'FECHA EMISIÓN', 'FECHA CONTABILIZACIÓN']
        # Obtener grupos de impuestos para el reporte
        tax_groups = self.env['account.tax.group'].search([('show_report', '=', True)], order="report_name")
        tax_col = 13
        tax_struct = {}
        # Mapear bases
        for tax_group in tax_groups:
            headers.append('BASE ' + tax_group.report_name.upper())
            tax_struct[tax_group.id] = {'base': tax_col}
            tax_col += 1
        # Mapear ivastax_col
        for tax_group in tax_groups:
            headers.append('MONTO ' + tax_group.report_name.upper())
            tax_struct[tax_group.id]['iva'] = tax_col
            tax_col += 1
        # LLenar el resto del texto de la cabecera
        headers += ['COD RET IVA']
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
        worksheet.write('C4', 'COMPRAS A2')
        row = 5
        last_col = 0
        # Mapear titulos
        for col, header in enumerate(headers):
            worksheet.merge_range(row, col, row + 1, col, header, formats['header_bg'])
            last_col += 1
        # Cabecera retenciones
        worksheet.merge_range(row, last_col, row, last_col + 5, 'RETENCIONES IVA', formats['header_bg'])
        worksheet.write(row + 1, last_col, 'RET 10%', formats['header_bg'])
        last_col += 1
        worksheet.write(row + 1, last_col, 'RET 20%', formats['header_bg'])
        last_col += 1
        worksheet.write(row + 1, last_col, 'RET 30%', formats['header_bg'])
        last_col += 1
        worksheet.write(row + 1, last_col, 'RET 50%', formats['header_bg'])
        last_col += 1
        worksheet.write(row + 1, last_col, 'RET 70%', formats['header_bg'])
        last_col += 1
        worksheet.write(row + 1, last_col, 'RET 100%', formats['header_bg'])
        last_col += 1
        # Cabecera restante
        headers2 = ['CÓDIGO RET. FUENTE', 'BASE IMP', 'PORCENTAJE DE RETENCIÓN FUENTE', 'VALOR RETENIDO', 'COMPROBANTE DE RETENCIÓN', 'AUT. RET.', 'FECHA DE RETENCIÓN',
                    'PAGO EXTERIOR - PAGO LOCAL', 'PAÍS DE PAGO', 'PARAÍSO FISCAL', 'ADOBLE TRIB. EN PAGO', 'SUJETO RET.', 'DIARIO CONTABLE', 'FORMATO DE PAGO',
                    'CTA. CONTABLE', 'REFERENCIA']
        # Mapear titulos 2
        for col, header in enumerate(headers2):
            worksheet.merge_range(row, last_col, row + 1, last_col, header, formats['header_bg'])
            last_col += 1
        # Mapear datos
        row += 1
        cont = 1
        for invoice in invoices:
            row += 1
            worksheet.write(row, 0, cont, formats['center'])
            # Obtener sustento tributario
            tax_supports = set()
            for line in invoice.invoice_line_ids:
                for tax in line.tax_ids:
                    if tax.l10n_ec_code_taxsupport:
                        tax_supports.add(tax.l10n_ec_code_taxsupport)
            # Convertir en string separado por coma
            tax_support = ', '.join(tax_supports)
            worksheet.write(row, 1, tax_support, formats['center'])
            worksheet.write(row, 2, invoice.partner_id.l10n_latam_identification_type_id.name or '', formats['center'])
            worksheet.write(row, 3, invoice.partner_id.vat or '', formats['border'])
            worksheet.write(row, 4, invoice.partner_id.complete_name or '', formats['border'])
            worksheet.write(row, 5, invoice.partner_id.l10n_ec_taxpayer_type_id.name if invoice.partner_id.l10n_ec_taxpayer_type_id else '', formats['border'])
            worksheet.write(row, 6, 'SI' if invoice.partner_id.l10n_ec_related_party else 'NO', formats['center'])
            subjet_type = ''
            if invoice.partner_id.company_type == 'person':
                subjet_type = 'Persona Natural'
            elif invoice.partner_id.company_type == 'company':
                subjet_type = 'Empresa'
            worksheet.write(row, 7, subjet_type, formats['border'])
            worksheet.write(row, 8, invoice.l10n_latam_document_type_id.name, formats['center'])
            worksheet.write(row, 9, invoice.name or '', formats['border'])
            worksheet.write(row, 10, invoice.l10n_ec_authorization_number or '', formats['border'])
            worksheet.write(row, 11, invoice.invoice_date.strftime("%d/%m/%Y") or '', formats['border'])
            worksheet.write(row, 12, invoice.date.strftime("%d/%m/%Y") or '', formats['border'])
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
                    worksheet.write(row, tax_struct[tax_group.id]['base'], base_amount or 0.00, formats['number'])
                    worksheet.write(row, tax_struct[tax_group.id]['iva'], iva_amount or 0.00, formats['number'])
                else:
                    worksheet.write(row, tax_struct[tax_group.id]['base'], 0.00, formats['number'])
                    worksheet.write(row, tax_struct[tax_group.id]['iva'], 0.00, formats['number'])
            # Retenciones
            retentions = self._get_retentions_data(invoice)
            iva_tax_groups = self.env['account.tax.group'].search([('type_ret', 'in', ['withholding_iva_purchase', 'withholding_iva_sales'])])
            rent_tax_groups = self.env['account.tax.group'].search([('type_ret', 'in', ['withholding_rent_purchase', 'withholding_rent_sales'])])
            cod_ret_iva = ''
            cod_ret_fuente = ''
            percent_ret_fuente = ''
            ret_10 = ret_20 = ret_30 = ret_50 = ret_70 = ret_100 = 0.00
            ret_name = ''
            ret_aut = ''
            ret_date = ''
            for retention in retentions:
                # Nombre retencion
                if ret_name:
                    ret_name += ', ' + retention.name
                else:
                    ret_name = retention.name
                # Autorizacion retencion
                if ret_aut:
                    ret_aut += ', ' + retention.l10n_ec_authorization_number
                else:
                    ret_aut = retention.l10n_ec_authorization_number
                # Fecha retencion
                if ret_date:
                    ret_date += ', ' + retention.l10n_ec_withhold_date.strftime('%d/%m/%Y')
                else:
                    ret_date = retention.l10n_ec_withhold_date.strftime('%d/%m/%Y')
                for line in retention.l10n_ec_withhold_line_ids:
                    for tax in line.tax_ids:
                        if tax.tax_group_id:
                            percent = abs(tax.amount)
                            ret_amount = abs(line.l10n_ec_withhold_tax_amount)
                            tax_code = (tax.l10n_ec_code_ats or tax.l10n_ec_code_applied or tax.l10n_ec_code_base or '')
                            # IVA
                            if tax.tax_group_id.id in iva_tax_groups.ids:
                                # Codigo retencion iva
                                if cod_ret_iva:
                                    cod_ret_iva += ', ' + tax_code
                                else:
                                    cod_ret_iva = tax_code
                                # Sumar al acumulador según porcentaje
                                if percent == 10:
                                    ret_10 += ret_amount
                                elif percent == 20:
                                    ret_20 += ret_amount
                                elif percent == 30:
                                    ret_30 += ret_amount
                                elif percent == 50:
                                    ret_50 += ret_amount
                                elif percent == 70:
                                    ret_70 += ret_amount
                                elif percent == 100:
                                    ret_100 += ret_amount
                            # FUENTE
                            elif tax.tax_group_id.id in rent_tax_groups.ids:
                                # Codigo retencion fuente
                                if cod_ret_fuente:
                                    cod_ret_fuente += ', ' + tax_code
                                else:
                                    cod_ret_fuente = tax_code
                                # Porcentaje de retencion
                                if percent_ret_fuente:
                                    percent_ret_fuente += ', ' + str(abs(tax.amount))
                                else:
                                    percent_ret_fuente = str(abs(tax.amount))
            # Cod Ret iva
            worksheet.write(row, tax_col, cod_ret_iva, formats['center'])
            # Retenciones IVA
            worksheet.write(row, tax_col+1, ret_10, formats['number'])
            worksheet.write(row, tax_col+2, ret_20, formats['number'])
            worksheet.write(row, tax_col+3, ret_30, formats['number'])
            worksheet.write(row, tax_col+4, ret_50, formats['number'])
            worksheet.write(row, tax_col+5, ret_70, formats['number'])
            worksheet.write(row, tax_col+6, ret_100, formats['number'])
            # cod Ret Fuente
            worksheet.write(row, tax_col+7, cod_ret_fuente, formats['center'])
            worksheet.write(row, tax_col+8, invoice.amount_untaxed, formats['number'])
            worksheet.write(row, tax_col+9, percent_ret_fuente, formats['center'])
            ret_amount = ret_10 + ret_20 + ret_30 + ret_50 + ret_70 + ret_100
            worksheet.write(row, tax_col+10, ret_amount, formats['number'])
            worksheet.write(row, tax_col+11, ret_name, formats['center'])
            worksheet.write(row, tax_col+12, ret_aut, formats['number'])
            worksheet.write(row, tax_col+13, ret_date, formats['center'])
            # Posicion fiscal
            worksheet.write(row, tax_col+14, invoice.fiscal_position_id.name if invoice.fiscal_position_id else '', formats['center'])
            payment_country = 'NA'
            payment_country_haven = 'NA'
            if invoice.fiscal_position_id and invoice.fiscal_position_id.country_id:
                payment_country = invoice.fiscal_position_id.country_id.name
                if invoice.fiscal_position_id.country_id.l10n_ec_code_tax_haven:
                    payment_country_haven = invoice.fiscal_position_id.country_id.l10n_ec_code_tax_haven
            worksheet.write(row, tax_col+15, payment_country, formats['center'])
            worksheet.write(row, tax_col+16, payment_country_haven, formats['center'])
            worksheet.write(row, tax_col+17, 'NA', formats['center'])
            worksheet.write(row, tax_col+18, 'NA', formats['center'])
            worksheet.write(row, tax_col+19, invoice.journal_id.name, formats['center'])
            worksheet.write(row, tax_col+20, invoice.l10n_ec_sri_payment_id.name if invoice.l10n_ec_sri_payment_id else '', formats['center'])
            # Obtener cuenta contable
            account_name = ''
            for line in invoice.line_ids:
                if line.account_id.account_type == 'liability_payable':
                    account_name = line.account_id.code
                    break
            worksheet.write(row, tax_col+21, account_name, formats['center'])
            worksheet.write(row, tax_col+22, invoice.ref, formats['center'])
            cont += 1
        workbook.close()
        output.seek(0)
        return output.read()