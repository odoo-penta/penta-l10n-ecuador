# -*- coding: utf-8 -*-

from odoo import fields, models


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