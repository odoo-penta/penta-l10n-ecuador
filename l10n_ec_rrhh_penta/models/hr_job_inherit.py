# -*- coding: utf-8 -*-
from odoo import models, fields

class HrJob(models.Model):
    _inherit = "hr.job"

    iess_sector_code = fields.Char(
        string="Código sectorial IESS",
        help="Código sectorial IESS (CODIGO_CARGO)."
    )

    _sql_constraints = [
        # opcional, quita si puedes tener el mismo código en varios cargos
        ('iess_sector_code_unique', 'unique(iess_sector_code)',
         'El Código sectorial IESS ya existe en otro puesto.')
    ]
