# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    program_type = fields.Selection([
        ('coupons', 'Coupons'),
        ('gift_card', 'Gift Card'),
        ('loyalty', 'Loyalty Cards'),
        ('promotion', 'Promotions'),
        ('ewallet', 'eWallet'),
        ('promo_code', 'Discount Code'),
        ('buy_x_get_y', 'Buy X Get Y'),
        ('next_order_coupons', 'Next Order Coupons'),
        ('financing_promotion', 'Financing promotion')],
        default='promotion', required=True,
    )
    
    @api.model
    def _program_items_name(self):
        return {
            'coupons': _('Coupons'),
            'promotion': _('Promos'),
            'gift_card': _('Gift Cards'),
            'loyalty': _('Loyalty Cards'),
            'ewallet': _('eWallets'),
            'promo_code': _('Discounts'),
            'buy_x_get_y': _('Promos'),
            'next_order_coupons': _('Coupons'),
            'financing_promotion': _('Financing promotion'),
        }