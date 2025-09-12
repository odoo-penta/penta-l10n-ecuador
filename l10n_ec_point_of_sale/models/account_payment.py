# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _


class FinanceCard(models.Model):
    _name = 'finance.card'
    _description = 'Credit/Debit Card'
    _order = 'name desc'
    
    name = fields.Char()
    card_type = fields.Selection([('debit', 'Debit'), ('credit', 'Credit')], string="Card type")


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    bank_reference = fields.Char(string="Bank reference")
    card = fields.Many2one('finance.card', string="Card")
    card_payment_type = fields.Selection(
        [('debit', 'Debit'),
         ('current', 'Current'),
         ('deferred_with_interest', 'Deferred with interest'),
         ('deferred_without_interest', 'Deferred without interest')], string="Payment type"
    )
    number_months = fields.Integer(string="Number of months")
    number_lot = fields.Char()
    authorization_number = fields.Char(string="Authorization number")
    bank_id = fields.Many2one("res.partner.bank")
