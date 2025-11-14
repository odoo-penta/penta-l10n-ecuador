# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResPartnerType(models.Model):
    _name = 'res.partner.type'
    
    name = fields.Char(tracking=True)
    active = fields.Boolean(
        'Active', default=True, tracking=True,
        help="By unchecking the active field, you may hide an customer type you will not use.")
    
class ResPartnerProfile(models.Model):
    _name = 'res.partner.profile'
    
    name = fields.Char(tracking=True)
    active = fields.Boolean(
        'Active', default=True, tracking=True,
        help="By unchecking the active field, you may hide an customer profile you will not use.")

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    is_customer = fields.Boolean(tracking=True)
    customer_type = fields.Many2one('res.partner.type', tracking=True)
    customer_profile = fields.Many2one('res.partner.profile', required=True, tracking=True)
