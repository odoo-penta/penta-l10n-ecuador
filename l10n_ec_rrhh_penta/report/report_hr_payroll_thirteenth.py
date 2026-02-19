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
        header_bold = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#e8c3e7', 'text_wrap': True})
        bold = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        # Formato titulos ingresos/gastos
        header_fmt_income = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#98a0d4', 'text_wrap': True})
        header_fmt_expense = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#bdbdbd', 'text_wrap': True})
        header_fmt_provision = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#aed4a5', 'text_wrap': True})
        # Codigos categorias ingresos/gastos
        c_incomes = ['BASICEC', 'BASIC', 'HOREXS', 'VACT', 'GROSS', 'BENFSO', 'BONO', 'COMSD', 'SUBSIDIOS', 'SUBT_SUBSIDIOS', 'TOTINGOTROS']
        c_expenses = ['DEDUD', 'CONALM']
        c_provision = ['EMC', 'DTER']
     
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
                'Décimo Tercero Provisionado',
                'Valor décimo',
                'Décimo Tercer Mensualizado',
                'Anticipo Décimo Tercero',
                'Décimo Tercero Neto a pagar'
            ]
            for header in headers:
                sheet.write(row, column, header, header_base)
                if header in ('Nombre', 'Cargo', 'Departamento', 'Sección Contable'):
                    width_col = _calc_col_width(header, min_width=50)
                elif header in ('Nro días trabajados'):
                    width_col = _calc_col_width(header, max_width=10)
                else:
                    width_col = _calc_col_width(header)
                sheet.set_column(column, column, width_col)
                column += 1
            