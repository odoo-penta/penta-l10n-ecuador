# l10n_ec_rrhh – interno Penta Lab
from odoo import models, fields

class HrPaymentMode(models.Model):
    _name = "hr.payment.mode"
    _description = "Modo de pago (Empleado)"
    _order = "sequence, name"

    name = fields.Char(string="Nombre", required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "El nombre del modo de pago debe ser único."),
    ]
