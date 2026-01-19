# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from datetime import date

def ec_validate_cedula(ced):
        if not ced or len(ced) != 10 or not ced.isdigit():
            return False
        prov = int(ced[0:2])
        if prov < 1 or prov > 24:
            return False
        if int(ced[2]) >= 6:
            return False
        coef = [2,1,2,1,2,1,2,1,2]
        total = 0
        for i in range(9):
            prod = int(ced[i]) * coef[i]
            if prod >= 10:
                prod -= 9
            total += prod
        ver = (10 - (total % 10)) % 10
        return ver == int(ced[9])

class L10nEcPtbFamilyDependents(models.Model):
    _inherit = "l10n_ec.ptb.family.dependents"
    _order = "employee_id, relationship, name"

    employee_id = fields.Many2one("hr.employee", string="Empleado", required=True, ondelete="cascade")
    vat = fields.Char(string="Número de identificación", required=True, size=13)
    gender = fields.Selection([("male", "Masculino"), ("female", "Femenino")], string="Sexo")
    use_for_income_tax = fields.Boolean(string="Usar impuesto a la renta")
    is_child = fields.Boolean(string="¿Es hijo/a?")
    is_permanent_charge = fields.Boolean(string="Carga permanente")
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        emp_id = self.env.context.get("default_employee_id")
        if emp_id:
            res["employee_id"] = emp_id
        return res

    @api.onchange('disability')
    def _onchange_disability(self):
        if self.disability:
            self.is_permanent_charge = True

    @api.constrains("relationship", "employee_id")
    def _check_spouse_unique(self):
        for rec in self:
            if rec.relationship == "spouse":
                count_spouse = self.search_count([
                    ("id", "!=", rec.id),
                    ("employee_id", "=", rec.employee_id.id),
                    ("relationship", "=", "spouse"),
                ])
                if count_spouse:
                    raise ValidationError("No puede haber más de un cónyuge en las cargas familiares para el mismo empleado.")
                
    # NUEVO: validar cédula y evitar duplicado de cédula por empleado
    @api.constrains("vat", "employee_id")
    def _check_vat_unique_and_valid(self):
        for rec in self:
            if rec.vat:
                if not ec_validate_cedula(rec.vat):
                    raise ValidationError("La cédula del dependiente no es válida.")
                clash = self.search_count([
                    ("id", "!=", rec.id),
                    ("employee_id", "=", rec.employee_id.id),
                    ("vat", "=", rec.vat),
                ])
                if clash:
                    raise ValidationError("Ya existe una carga familiar con la misma cédula para este empleado.")
            else:
                raise ValidationError("Debe ingresar una cédula del dependiente.")    
