# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _


class CashPaymentMethod(models.Model):
    _name = 'cash.payment.method'
    _description = 'Payment Method for POS'
    _order = 'name desc'
    
    name = fields.Char(required=True)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True)
    payment_info_type = fields.Selection(related='journal_id.payment_info_type', string='Payment information', store=True, readonly=True)
    l10n_ec_sri_payment_id = fields.Many2one('l10n_ec.sri.payment', string="SRI Payment Method", required=True)
    card = fields.Many2one('account.cars', string="Card")