# -*- coding: utf-8 -*-

from odoo import models, fields


class HrSubstituteType(models.Model):
    _name = "hr.substitute.type"
    _description = "Tipo de sustituto"
    
    _sql_constraints = [
        ("name_uniq", "unique(name)", "La descripción de sustituto debe ser única."),
    ]

    name = fields.Char(string="Descripción de sustituto", required=True, translate=True)
    active = fields.Boolean(default=True)

    
