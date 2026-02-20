# -*- coding: utf-8 -*-
from odoo import models,fields
import io
import xlsxwriter

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.addons.penta_base.reports.xlsx_formats import get_xlsx_formats, _calc_col_width

# Formato de fecha deseado
date_format = "%d-%m-%Y"

class ReportThirteenthXlsx(models.AbstractModel):
    _name = 'report.l10n_ec_rrhh_penta.report_thirteenth_xlsx'
    _description = 'report.l10n_ec_rrhh_penta.report_thirteenth_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, payslip_runs):
        # Formatos
        formats = get_xlsx_formats(workbook)
        header_base = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_color': '#FFFFFF', 'bg_color': '#242d6e', 'text_wrap': True})
        bold = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
     
        for payslip_run in payslip_runs:
            # Crear la hoja de Excel
            sheet = workbook.add_worksheet('Reporte de Nomina')
            # Obtener los payslips
            hr_payslips = payslip_run.slip_ids
            # <======== REPORTE DE NOMINA EN EXCEL ========>
            # Cabecera
            sheet.merge_range('A1:C1', payslip_run.company_id.name)
            sheet.merge_range('A2:C2', 'Décimo Tercer Sueldo')
            sheet.write('A4', 'Desde')
            sheet.write('B4', payslip_run.date_start.strftime(date_format) or '')
            sheet.write('A5', 'Hasta')
            sheet.write('B5', payslip_run.date_end.strftime(date_format) or '')
            sheet.write('A6', 'Generado')
            sheet.write('B6', fields.Date.today().strftime(date_format))
            # Datos de la tabla
            row = 7
            column = 0
            headers = [
                'Cédula',
                'Apellidos y Nombres',
                'Fecha de contrato',
                'Sueldo EC',
                'Dias Laborados',
                'Puesto de trabajo',
                'Departamento',
                'Sección Contable',
                'Tipo de pago',
                'Décimo Tercero Provisionado',
                'Base impobles IESS',
                'Valor décimo',
                'Décimo Tercer Mensualizado',
                'Anticipo Décimo Tercero',
                'Décimo Tercero Neto a pagar'
            ]
            for header in headers:
                sheet.write(row, column, header, header_base)
                if header in ('Apellidos y Nombres', 'Puesto de trabajo', 'Departamento', 'Sección Contable'):
                    width_col = _calc_col_width(header, min_width=50)
                elif header in ('Fecha de contrato', 'Sueldo EC', 'Dias Laborados'):
                    width_col = _calc_col_width(header, max_width=10)
                else:
                    width_col = _calc_col_width(header)
                sheet.set_column(column, column, width_col)
                column += 1
                
            for payslip in hr_payslips:
                row += 1
                column = 0
                # Obtener datos del empleado
                employee = payslip.employee_id
                contract = payslip.contract_id
                if contract.l10n_ec_ptb_thirteenth_fund_paid == 'accumulated':
                    thirteenth_fund_paid = 'Acumulado'
                elif contract.l10n_ec_ptb_thirteenth_fund_paid == 'monthly':
                    thirteenth_fund_paid = 'Mensualizado'
                else:
                    thirteenth_fund_paid = 'No definido'
                thirteenth_accumulated = payslip.line_ids.filtered(lambda l: l.code == 'DTERACU').amount
                thirteenth_monthly = payslip.line_ids.filtered(lambda l: l.code == 'DTERMENSU').amount
                thirteenth_advance = payslip.line_ids.filtered(lambda l: l.code == 'THIRTEENTH_ADVANCE').amount
                thirteenth_net = payslip.line_ids.filtered(lambda l: l.code == 'DTERNETO').amount
                # Datos básicos
                sheet.write(row, column, employee.identification_id or '', bold)
                column += 1
                sheet.write(row, column, employee.name or '', bold)
                column += 1
                sheet.write(row, column, contract.date_start.strftime(date_format) if contract.date_start else '', bold)
                column += 1
                sheet.write(row, column, contract.wage or 0.0, formats['number'])
                column += 1
                sheet.write(row, column, min(payslip.days_of_month_ec, 360), formats['number'])
                column += 1
                sheet.write(row, column, contract.job_id.name or '', bold)
                column += 1
                sheet.write(row, column, contract.department_id.name or '', bold)
                column += 1
                sheet.write(row, column, contract.account_section_id.name or '', bold)
                column += 1
                sheet.write(row, column, thirteenth_fund_paid, bold)
                column += 1
                sheet.write(row, column, thirteenth_accumulated, formats['number'])
                column += 1
                sheet.write(row, column, thirteenth_accumulated + thirteenth_monthly, formats['number'])
                column += 1
                sheet.write(row, column, (thirteenth_accumulated + thirteenth_monthly)/12, formats['number'])
                column += 1
                sheet.write(row, column, thirteenth_monthly, formats['number'])
                column += 1
                sheet.write(row, column, thirteenth_advance, formats['number'])
                column += 1
                sheet.write(row, column, thirteenth_net, formats['number'])
            