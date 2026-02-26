# -*- coding: utf-8 -*-
from odoo import models, fields

class HrDisabilityType(models.Model):
    _name = "hr.disability.type"
    _description = "Tipo de discapacidad"

    name = fields.Char(string="Descripción de discapacidad", required=True, translate=True)
    notes = fields.Text(string="Notas")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "La descripción de discapacidad debe ser única."),
    ]
