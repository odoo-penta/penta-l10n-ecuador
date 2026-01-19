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
    _name = "l10n_ec.ptb.family.dependents"
    _description = "Cargas Familiares"
    _order = "employee_id, relationship, name"

    employee_id = fields.Many2one("hr.employee", string="Empleado", required=True, ondelete="cascade")
    vat = fields.Char(string="Número de identificación", required=True, size=13)
    gender = fields.Selection([("male", "Masculino"), ("female", "Femenino")], string="Sexo")
    use_for_income_tax = fields.Boolean(string="Usar impuesto a la renta")
    is_child = fields.Boolean(string="¿Es hijo/a?")
    is_permanent_charge = fields.Boolean(string="Carga permanente")
    name = fields.Char(string="Nombre", required=True)
    birthdate = fields.Date(string="Fecha de nacimiento", required=True)
    phone = fields.Char(string="Teléfono", size=20)
    address = fields.Char(string="Dirección")
    disability = fields.Boolean(string="Discapacidad")
    relationship = fields.Selection([
        ("spouse", "Cónyuge"),
        ("children", "Hijo/a"),
        ("parents", "Padre/Madre"),
        ("other", "Otro"),
    ], string="Parentesco", required=True)
    age_years = fields.Integer(string="Edad (años)", compute="_compute_age", store=False)
    employee_id = fields.Many2one('hr.employee', string="Empleado")
    
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
            
    @api.depends("birthdate")
    def _compute_age(self):
        today = date.today()
        for rec in self:
            if rec.birthdate and rec.birthdate <= today:
                delta = relativedelta(today, rec.birthdate)
                rec.age_years = delta.years
            else:
                rec.age_years = 0

    @api.constrains('birthdate')
    def _check_birthdate(self):
        for record in self:
            if record.birthdate and record.birthdate > date.today():
                raise ValidationError("La fecha de nacimiento no puede ser mayor a la fecha actual.")
            

    @api.constrains('relationship', 'employee_id')
    def _check_family_dependents_limit(self):
        for record in self:
            employee = record.employee_id

            # Verificar número de cónyuges
            spouse_count = len(employee.family_dependent_ids.filtered(lambda x: x.relationship == 'spouse'))
            if spouse_count > 1:
                raise ValidationError("No puede haber más de un cónyuge en las cargas familiares.")

            # Verificar estado civil
            if (employee.marital != 'married' and employee.marital != 'cohabitant') and spouse_count:
                employee.marital = 'married'
                employee.spouse_complete_name = record.name
                employee.spouse_birthdate = record.birthdate
                employee.vat = record.vat
            
            # Verificar si el cónyuge fue eliminado
            if spouse_count == 0:
                employee.marital = 'single'  # Cambia el estado civil
                employee.spouse_complete_name = False  # Limpiar el nombre del cónyuge
                employee.spouse_birthdate = False  # Limpiar la fecha de nacimiento
                employee.vat = False  # Limpiar el número de identificación
