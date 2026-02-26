# -*- coding: utf-8 -*-
from odoo import models, fields

class HrEducationLevel(models.Model):
    _name = "hr.education.level"
    _description = "Nivel de Educación"

    name = fields.Char(string="Nivel", required=True, translate=True)
    code = fields.Char(string="Código", help="Código interno (opcional).")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "El nombre del nivel de educación debe ser único."),
    ]
