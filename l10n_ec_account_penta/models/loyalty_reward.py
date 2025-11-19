# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'
    
    interest = fields.Integer(string='Interest (%)', default=0)
    months_of_grace = fields.Integer(string='Months of Grace', default=0)
    apply_interest_grace = fields.Boolean(string='Apply Interest Grace', default=False)
    minimum_fee = fields.Monetary(string='Minimum Fee', default=0.0)
    apply_payment_terms = fields.Many2one('account.payment.term', string='Apply Payment Terms', domain="[('generate_installments', '=', True), ('installments_number', '>', 0)]")