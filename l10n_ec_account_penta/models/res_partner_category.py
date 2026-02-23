from odoo import fields, models


class ResPartnerCategory(models.Model):
    _inherit = "res.partner.category"

    contact_type = fields.Selection(
        [
            ("customer", "Cliente"),
            ("provider", "Proveedor"),
            ("other", "Otro"),
        ],
        string="Tipo de Contacto",
        default="other",
    )
