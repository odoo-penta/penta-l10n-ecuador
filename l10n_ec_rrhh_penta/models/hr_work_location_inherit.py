# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class HrWorkLocation(models.Model):
    _inherit = "hr.work.location"

    branch_code = fields.Char(
        string="Código de sucursal",
        size=3,
        help="Código corto de 3 caracteres (p.ej. 001, ABC)."
    )

    _sql_constraints = [
        # Evita duplicados por compañía (ajusta si no usas multi-company)
        ('branch_code_company_unique',
         'unique(company_id, branch_code)',
         'El código de sucursal debe ser único por compañía.')
    ]

    # -------- Normalización (NO validar aquí) ----------
    def _normalize_branch_vals(self, vals):
        vals = dict(vals)
        code = vals.get('branch_code')
        if code:
            vals['branch_code'] = code.strip().upper()
        return vals

    @api.model
    def create(self, vals):
        vals = self._normalize_branch_vals(vals)
        return super().create(vals)

    def write(self, vals):
        vals = self._normalize_branch_vals(vals)
        return super().write(vals)

    # -------- Validación (NO escribir aquí) ----------
    @api.constrains('branch_code')
    def _check_branch_code(self):
        for rec in self:
            if not rec.branch_code:
                continue
            val = rec.branch_code.strip()
            # exactamente 3 caracteres numéricos
            if len(val) != 3 or not val.isdigit():
                raise ValidationError(
                    "El código de sucursal debe tener exactamente 3 caracteres numéricos."
                )

