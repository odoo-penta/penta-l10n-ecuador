# -*- coding: utf-8 -*-
from odoo import models,fields
import io
import xlsxwriter

from datetime import datetime, timedelta
from odoo.addons.penta_base.reports.xlsx_formats import get_xlsx_formats
from dateutil.relativedelta import relativedelta

# Formato de fecha deseado
date_format = "%d-%m-%Y"

class ReportPayrollXlsx(models.AbstractModel):
    _name = 'report.l10n_ec_rrhh_penta.report_payroll_xlsx'
    _description = 'report.l10n_ec_rrhh_penta.report_payroll_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, wizards):
        # Formatos
        formats = get_xlsx_formats(workbook)
     
        for wizard in wizards:
            # Crear la hoja de Excel
            sheet = workbook.add_worksheet('Reporte de Nomina')
            bold = workbook.add_format({'bold': True})
            # Domain base de los payslips
            domain = [
                ('company_id','=',wizard.company_id.id),
                ('state', '!=', 'cancel')
            ]
            # Dominio de lote
            if wizard.lote:
                domain.append(('payslip_run_id', '=', wizard.lote.id))
            else:
            # Dominio de fecha desde y hasta
                domain.append(('date_from', '>=', wizard.date_from))
                domain.append(('date_to', '<=', wizard.date_to))
            # Obtener los payslips según el dominio
            hr_payslips = self.env['hr.payslip'].search(domain, order='name asc')
            # <======== REPORTE DE NOMINA EN EXCEL ========>
            # Cabecera
            sheet.merge_range('A1:C1', wizard.company_id.name ,bold)
            sheet.merge_range('A2:C2', 'Nómina de Colaboradores',bold)
            sheet.write('A4', 'Desde',bold)
            sheet.write('B4', hr_payslips[0].payslip_run_id.date_start.strftime(date_format) or '',bold)
            sheet.write('A5', 'Hasta',bold)
            sheet.write('B5', hr_payslips[0].payslip_run_id.date_end.strftime(date_format) or '',bold)
            sheet.write('A6', 'Estructura',bold)
            sheet.write('B6', 'Rol de Pagos')
            sheet.write('A7', 'Departamento',bold)
            sheet.write('B7', 'Todos los Departamentos')
            sheet.write('A8', 'Empleados',bold)
            sheet.write('B8', 'Todos los Empleados')
            sheet.write('A9', 'Generado',bold)
            sheet.write('B9', fields.Date.today().strftime(date_format))
            # Datos de la tabla
            row = 10
            column = 0
            sheet.write(row, column, 'Período/mes', formats['header_bg'])
            column += 1
            sheet.write(row, column, 'Ref Rol', formats['header_bg'])
            column += 1
            sheet.write(row, column, 'Nombre', formats['header_bg'])
            column += 1
            sheet.write(row, column, 'Identificación', formats['header_bg'])
            column += 1
            sheet.write(row, column, 'Fecha de ingreso', formats['header_bg'])
            column += 1
            sheet.write(row, column, 'Cargo', formats['header_bg'])
            column += 1
            sheet.write(row, column, 'Departamento', formats['header_bg'])
            column += 1
            sheet.write(row, column, 'Sección Contable', formats['header_bg'])
            column += 1
            sheet.write(row, column, 'Nro días trabajados', formats['header_bg'])
            column += 1
            salary_rules = self.env['hr.salary.rule'].search([('appears_on_payroll_report', '=', True)], order='sequence asc')
            # Mapear dinamicamente cabeceras de reglas
            for rule in salary_rules:
                sheet.write(row, column, rule.name, bold)
                column += 1
            row += 1
            # Recorrer los payslips y escribir los datos
            for hr_payslip in hr_payslips:
                column = 0
                sheet.write(row, column, hr_payslip.payslip_run_id.name or '') # Periodo/mes
                column += 1
                sheet.write(row, column, hr_payslip.number or '') # Ref Rol
                column += 1
                sheet.write(row, column, hr_payslip.employee_id.name or '') # Nombre empleado
                column += 1
                sheet.write(row, column, hr_payslip.employee_id.identification_id or '')  # Identificacion empleado
                column += 1
                sheet.write(row, column, hr_payslip.employee_id.first_contract_date.strftime(date_format) if hr_payslip.employee_id.first_contract_date else '') # Fecha de ingreso
                column += 1
                sheet.write(row, column, hr_payslip.employee_id.job_title or '') # Cargo del empleado
                column += 1
                sheet.write(row, column, hr_payslip.department_id.name or '') # Departamento
                column += 1
                sheet.write(row, column, hr_payslip.contract_id.account_section_id.name if hr_payslip.contract_id.account_section_id else '') # Seccion contable
                column += 1
                # Acceder a los días trabajados relacionados
                worked_days = 0
                worked_day_lines = hr_payslip.worked_days_line_ids
                for wline in worked_day_lines:
                    if(wline.code in ('WORK100','WORK110','WORK120','LEAVE110','LEAVE120','ILLNESSIESS50','ILLNESSIESS66','ILLNESSIESS75')):
                        worked_days += wline.number_of_days
                sheet.write(row, column, min(worked_days, 30)) # Nro dias trabajados
                column += 1
                # Mapear dinamicamente valores de reglas
                for rule in salary_rules:
                    sheet.write(row, column, hr_payslip.line_ids.filtered(lambda line, rule=rule: line.salary_rule_id.id == rule.id).amount or 0)
                    column += 1
                row += 1
            