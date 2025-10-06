# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HrWorkLocation(models.Model):
    _inherit = "hr.work.location"

    branch_code = fields.Char(string="Código de sucursal", size=3)

    @api.constrains("branch_code")
    def _check_branch_code(self):
        for rec in self:
            if rec.branch_code:
                val = rec.branch_code.strip().upper()
                if len(val) != 3 or not val.isalnum():
                    raise ValidationError("El código de sucursal debe tener exactamente 3 caracteres alfanuméricos.")
                rec.branch_code = val
