# -*- coding: utf-8 -*-
from odoo import fields, models


class PentaVacationReportLine(models.TransientModel):
    _name = "penta.vacation.report.line"
    _description = "Línea de reporte de Vacaciones (transitorio)"
    _order = "employee_name"

    wizard_id = fields.Many2one("penta.vacation.report.wizard", ondelete="cascade")

    employee_id = fields.Many2one("hr.employee", string="Empleado (ID)")
    employee_name = fields.Char(string="Empleado")
    identification = fields.Char(string="Identificación")
    company_name = fields.Char(string="Compañía")
    department_name = fields.Char(string="Departamento")
    job_name = fields.Char(string="Puesto")
    leave_type_name = fields.Char(string="Tipo de ausencia")
    allocated = fields.Float(string="Asignado (días)", digits=(16, 2))
    taken = fields.Float(string="Tomado (días)", digits=(16, 2))
    balance = fields.Float(string="Saldo (días)", digits=(16, 2))
