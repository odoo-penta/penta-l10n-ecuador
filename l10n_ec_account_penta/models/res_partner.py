# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResPartnerType(models.Model):
    _name = 'res.partner.type'
    
    name = fields.Char()
    active = fields.Boolean(
        'Active', default=True,
        help="By unchecking the active field, you may hide an customer type you will not use.")

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    is_customer = fields.Boolean()
    customer_type = fields.Many2one('res.partner.type')
