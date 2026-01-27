# -*- coding: utf-8 -*-
from odoo import models,fields
import io
import xlsxwriter

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Formato de fecha deseado
date_format = "%d-%m-%Y"

class CustomerXlsx(models.AbstractModel):
    _name = 'report.l10n_ec_rrhh_penta.report_payroll_xlsx'
    _description = 'report.l10n_ec_rrhh_penta.report_payroll_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, wizards):

        type_account_translations = {
            'savings': 'Cuenta de ahorros',
            'checking': 'Cuenta Corriente',
        }
        
        # background_green = workbook.add_format({'bg_color': '#C0FFC8'})
        background_green_c = workbook.add_format({'bold': True, 'bg_color': '#C0FFC8'})
        background_blue = workbook.add_format({'bold': True, 'bg_color': '#C1FFFE'})
        background_green = workbook.add_format({'bold': True, 'bg_color': '#00FF31'})
        background_yellow = workbook.add_format({'bold': True, 'bg_color': '#FEFFC9'})
        background_orange = workbook.add_format({'bold': True, 'bg_color': '#FF9027'})
        background_purple = workbook.add_format({'bold': True, 'bg_color': '#C6C4FC'})
        background_red = workbook.add_format({'bold': True, 'bg_color': '#FF001C'})
     
        
        for wizard in wizards:
            
            sheet = workbook.add_worksheet('Reporte de Nomina')
            bold = workbook.add_format({'bold': True})


            # Merge cells for headers
            sheet.merge_range('A1:C1', wizard.company_id.name ,bold)
            sheet.merge_range('A2:C2', 'Nómina de Colaboradores',bold)
            sheet.write('A4', 'Desde',bold)
            sheet.write('A5', 'Hasta',bold)
            sheet.write('A6', 'Estructura',bold)
            sheet.write('B6', 'Rol de Pagos')
            sheet.write('A7', 'Departamento',bold)
            sheet.write('B7', 'Todos los Departamentos')
            sheet.write('A8', 'Empleados',bold)
            sheet.write('B8', 'Todos los Empleados')
            sheet.write('A9', 'Generado',bold)
            sheet.write('B9', fields.Date.today().strftime(date_format))
            sheet.merge_range('A10:A11', 'PERÍODO/MES', bold)  # Merges from A1 to C2
            sheet.merge_range('B10:B11', 'NRO', bold)
            sheet.merge_range('C10:C11', 'FECHA DE INGRESO', bold)
            sheet.merge_range('D10:D11', 'IDENTIFICACIÓN', bold)
            sheet.merge_range('E10:E11', 'CARGO', bold)
            sheet.merge_range('F10:F11', 'NOMBRE', bold)
            sheet.merge_range('G10:G11', 'CENTRO DE COSTO', bold)
            sheet.merge_range('H10:H11', 'DEPARTAMENTO', bold)
            sheet.merge_range('I10:I11', 'BANCO', bold)
            sheet.merge_range('J10:J11', '# DE CUENTA', bold)
            sheet.merge_range('K10:K11', 'TIPO DE CUENTA', bold)
            sheet.merge_range('L10:L11', 'NRO DIAS TRABAJADOS', bold)
            sheet.merge_range('M10:M11', 'NRO H25', bold)
            sheet.merge_range('N10:N11', 'NRO H50', bold)
            sheet.merge_range('O10:O11', 'NRO H100', bold)
            sheet.merge_range('P10:P11', 'SALARIO CONTRATADO', bold)  # Merges from Q1 to R2
            sheet.merge_range('Q10:W10', 'INGRESOS', background_green_c)
            sheet.write('Q11', 'Salario Nominal', background_green_c)
            sheet.write('R11', 'Horas Suplementarias', background_green_c)
            sheet.write('S11', 'Horas Extraordinarias', background_green_c)
            sheet.write('T11', 'Horas Nocturnas', background_green_c)
            sheet.write('U11', 'Bonificaciones por Cumplimiento', background_green_c)
            sheet.write('V11', 'Otros Ingresos', background_green_c)
            sheet.write('W11', 'TOTAL INGRESOS GRAVADOS IESS', background_green_c)
            sheet.merge_range('X10:AA10', 'OTROS INGRESOS', background_blue)
            sheet.write('X11', 'Fondos de Reserva Mensual', background_blue)
            sheet.write('Y11', 'Décimo Tercero Mensual', background_blue)
            sheet.write('Z11', 'Décimo Cuarto Mensual', background_blue)
            sheet.write('AA11', 'TOTAL OTROS INGRESOS', background_blue)
            sheet.merge_range('AB10:AB11', 'TOTAL INGRESOS(INGRESOS + OTROS INGRESOS)', background_green)
            sheet.merge_range('AC10:AO10', 'EGRESOS', background_yellow)
            sheet.write('AC11', 'IESS Personal', background_yellow)
            sheet.write('AD11', 'Seguro medico Confiamed', background_yellow)
            sheet.write('AE11', 'Parqueadero Empleados', background_yellow)
            sheet.write('AF11', 'Atrasos', background_yellow)
            sheet.write('AG11', 'Convenio Debito Rol', background_yellow)
            sheet.write('AH11', 'Impuesto a la Renta', background_yellow)
            sheet.write('AI11', 'Préstamo Quirografario a Reembolsar al IESS', background_yellow)
            sheet.write('AJ11', 'Préstamo Hipotecario a Reembolsar al IESS', background_yellow)
            sheet.write('AK11', 'Préstamo Empleado', background_yellow)
            sheet.write('AL11', 'Curso Inteligencia Artificial', background_yellow)
            sheet.write('AM11', 'Descuento de Moto', background_yellow)
            sheet.write('AN11', 'Permiso Médico', background_yellow)
            sheet.write('AO11', 'TOTAL EGRESOS', background_yellow)
            sheet.merge_range('AP10:AP11', 'SUELDOS A PAGAR', background_green)
            sheet.merge_range('AQ10:AW10', 'PROVISIONES', background_purple)
            sheet.write('AQ11', 'IESS Patronal', background_purple) 
            sheet.write('AR11', 'CCC', background_purple)
            sheet.write('AS11', 'Fondos de Reserva Acumulado', background_purple)
            sheet.write('AT11', 'Décimo Tercero Acumulado', background_purple)
            sheet.write('AU11', 'Décimo Cuarto Acumulado', background_purple)
            sheet.write('AV11', 'Provisión Vacaciones', background_purple)
            sheet.write('AW11', 'TOTAL PROVISIONES', background_purple)
            sheet.merge_range('AX10:AX11', 'COSTO EMPRESA', background_red)  # Merges from A1 to C2
            
            # Query invoices
            domain = [
                ('company_id','=',wizard.company_id.id),
                ('state', '!=', 'cancel')
            ]

            if wizard.lote:
                domain.append(('payslip_run_id', '=', wizard.lote.id))
                wizard.date_from = False  # Establece date_from en blanco
                wizard.date_to = False  # Establece date_to en blanco

            if wizard.date_from:
                domain.append(('date_from', '>=', wizard.date_from))
                sheet.write(3, 1, wizard.date_from.strftime(date_format) or '')
    
            if wizard.date_to:
                domain.append(('date_to', '<=', wizard.date_to))
                sheet.write(4, 1, wizard.date_to.strftime(date_format) or '')
                wizard.lote= False  # Establece date_from en blanco

            
            hr_payslips = self.env['hr.payslip'].search(domain, order='name asc')

             # Write dates once
            if hr_payslips:
                if wizard.lote.id:
                    sheet.write(3, 1, hr_payslips[0].payslip_run_id.date_start.strftime(date_format) or '')
                    sheet.write(4, 1, hr_payslips[0].payslip_run_id.date_end.strftime(date_format) or '')
                    

            # Write invoice data
            row = 11
            for hr_payslip in hr_payslips:
                # sheet.write(3, 1, hr_payslip.payslip_run_id.date_start.strftime(date_format) or '')
                # sheet.write(4, 1, hr_payslip.payslip_run_id.date_end.strftime(date_format) or '')
                sheet.write(row, 0, hr_payslip.payslip_run_id.name or '')
                sheet.write(row, 1, hr_payslip.number or '')
                # sheet.write(row, 2, hr_payslip.employee_id.first_contract_date.strftime(date_format) or '')
                sheet.write(row, 2, hr_payslip.employee_id.first_contract_date.strftime(date_format) if hr_payslip.employee_id.first_contract_date else '')
                sheet.write(row, 3, hr_payslip.employee_id.identification_id or '')
                sheet.write(row, 4, hr_payslip.employee_id.job_title or '')
                sheet.write(row, 5, hr_payslip.employee_id.name or '')

                sheet.write(row, 7, hr_payslip.department_id.name or '')
                sheet.write(row, 8, hr_payslip.employee_id.bank_account_id.bank_id.name or '')
                sheet.write(row, 9, hr_payslip.employee_id.bank_account_id.acc_number or '')

                type_account= type_account_translations.get(hr_payslip.employee_id.bank_account_id.type_account)
                sheet.write(row, 10, type_account or '')
                

                # Acceder a los días trabajados relacionados
                worked_days = hr_payslip.worked_days_line_ids
                for worked_day in worked_days:
                    if(worked_day.work_entry_type_id.id == 1):
                        sheet.write(row, 11, worked_day.number_of_days or 0)
                        sheet.write(row, 15, worked_day.amount or 0)
                        sheet.write(row, 16, worked_day.amount or 0)
                        sheet.write(row, 22, worked_day.amount or 0)
                        # row += 1
                
                # Acceder a las líneas del payslip relacionadas
                payslip_lines = hr_payslip.line_ids
                
                # Diccionario para mapear códigos a columnas
                code_to_column = {
                    'BONO': 20,
                    # 'RESV':23,
                    'OTROSING':21,
                    'DTERMEN':24,
                    'DCUARMEN':25,
                    'TOTING': 27,
                    'IESSPER': 28,
                    'SEGCONF': 29,
                    'PARQEM': 30,
                    'ATRA': 31,
                    'CONALM': 32,
                    'IMPRENTA': 33,
                    'QUIROGRAFARIO': 34,
                    'HIPOTECARIO': 35,
                    'PRESTEMPLE': 36,
                    'CURSOINTART':37,
                    'DESCMOTO':38,
                    'PERMED':39,
                    'TOTEGR': 40,
                    'NET': 41,
                    'EMC': 42,
                    'CCC': 44,
                    'DTER': 45,
                    'DCUAR': 46,
                    'PVC': 47,
                    # 'NET': 44,
                }

                # Inicializar todas las columnas a 0
                for column in code_to_column.values():
                    sheet.write(row, column, 0)

                # Lista de columnas que quieres inicializar a 0
                columns_to_initialize = [17,18,19,23, 42]

                # Inicializar las columnas 23 y 39 a 0
                for column in columns_to_initialize:
                    sheet.write(row, column, 0)

                # Variables para acumular los valores de las columnas que queremos sumar
                col_23_value = 0
                col_24_value = 0
                col_25_value = 0

                col_38_value = 0
                col_39_value = 0
                col_40_value = 0
                col_41_value = 0
                col_42_value = 0
                col_43_value = 0


                col_44_value = 0
                col_45_value = 0
                col_46_value = 0

                col_47_value = 0


                # Escribir datos de `hr.payslip.line`
                for payslip_line in payslip_lines:
                    sum_value=0
                    sum_value1=0
                    if payslip_line.date_from == hr_payslip.date_from:
                        if(payslip_line.salary_rule_id.id == 113):
                            col_23_value = payslip_line.total or 0
                            sheet.write(row, 23, payslip_line.total or '0')
                        if(payslip_line.salary_rule_id.id == 127):
                            col_42_value = payslip_line.total or 0
                            sheet.write(row, 42, payslip_line.total or '0')

                        column = code_to_column.get(payslip_line.code)
                        if column is not None:
                            total_value = payslip_line.total or 0
                            sheet.write(row, column, total_value)

                         # Sumar los valores de las columnas 23, 24, 25
                        if column == 24:
                            col_24_value = total_value
                        elif column == 25:
                            col_25_value = total_value
                        # elif column == 38:
                        #     col_38_value = total_value
                        elif column == 38:
                            col_38_value = total_value
                        elif column == 39:
                            col_39_value = total_value
                        elif column == 40:
                            col_40_value = total_value
                        elif column == 41:
                            col_41_value = total_value
                        # elif column == 42:
                        #     col_42_value = total_value
                        elif column == 43:
                            col_43_value = total_value
                        elif column == 44:
                            col_44_value = total_value
                        elif column == 45:
                            col_45_value = total_value
                        elif column == 46:
                            col_46_value = total_value
                        # elif column == 27:
                        #     col_45_value = total_value
                        elif column == 47:
                            col_47_value = total_value



                    # Sumar los valores de las columnas 23, 24 y 25
                    sum_value = col_23_value + col_24_value + col_25_value
                    sum_value1 = col_40_value + col_41_value + col_42_value + col_43_value + col_44_value + col_45_value 
                    sum_value2 = col_38_value + col_39_value + col_40_value + col_41_value + col_42_value + col_43_value + col_44_value + col_45_value + col_46_value
                    # Escribir la suma en la columna 26
                    sheet.write(row, 26, sum_value)     
                    sheet.write(row, 46, sum_value1)  
                    sheet.write(row, 47, sum_value2)  
                
                row += 1  # Add an empty row between different invoices

            