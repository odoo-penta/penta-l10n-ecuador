# -*- coding: utf-8 -*-

from odoo import models, fields


class HrSubstituteRelationship(models.Model):
    _name = "hr.substitute.relationship"
    _description = "TiParenteco del sustituto"
    
    _sql_constraints = [
        ("name_uniq", "unique(name)", "La descripción del parentezco debe ser única."),
    ]

    name = fields.Char(string="Descripción del parentesco", required=True, translate=True)
    active = fields.Boolean(default=True)
