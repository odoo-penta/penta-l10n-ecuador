# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'
    
    entry_percentage = fields.Float(string='Entry (%)', default=0)
    risk_percentage = fields.Float(string='Risk (%)', default=0)
    interest = fields.Float(string='Interest (%)', default=0)
    months_of_grace = fields.Integer(string='Months of Grace', default=0)
    apply_interest_grace = fields.Boolean(string='Apply Interest Grace', default=False)
    minimum_fee = fields.Monetary(string='Minimum Fee', default=0.0)
    apply_payment_terms = fields.Many2one('account.payment.term', string='Apply Payment Terms', domain="[('generate_installments', '=', True), ('installments_number', '>', 0)]")
    payment_period = fields.Integer(
        comodel_name='account.payment.term',
        related='apply_payment_terms.installments_number',
        string='Payment Period (Months)',
        readonly=True,
    )