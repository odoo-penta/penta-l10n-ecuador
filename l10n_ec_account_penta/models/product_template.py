# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    financing_product = fields.Boolean(
        string="Financing product"
    )
    financing_interest_product = fields.Boolean(
        string="Financing interest product"
    )

    @api.constrains('financing_interest_product')
    def _check_unique_financing_interest_product(self):
        for record in self:
            if record.financing_interest_product:
                # Buscar otros productos que tengan activo este check
                existing = self.env['product.template'].search([
                    ('financing_interest_product', '=', True),
                    ('id', '!=', record.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_(
                        "Action not allowed. The product '%s' is already configured as 'Financing Interest Product'. "
                        "Please deactivate it first to assign a new one."
                        % existing.name
                    ))