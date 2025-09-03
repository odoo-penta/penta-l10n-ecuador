from odoo import models, fields

class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'

    tax_type = fields.Selection([
        ('iva', 'IVA'),
        ('renta', 'Renta'),
    ], string="Tipo de Impuesto")
