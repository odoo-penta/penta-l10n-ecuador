# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    journal_type = fields.Selection(related='journal_id.type', readonly=True, string="Journal Type")
    bank_reference = fields.Char(string="Bank reference")
    used_card_id = fields.Many2one(
        'account.cards',
        string='Tarjeta usada',
        domain=[('active', '=', True)],
        ondelete='restrict',
        index=True,
        readonly=False,
        store=True,
    )
    card_payment_type = fields.Selection(
        selection=[
        ('Débito', 'Débito'),
        ('Corriente', 'Corriente'),
        ('Diferido con interés', 'Diferido con interés'),
        ('Diferido sin interés', 'Diferido sin interés')
        ], string="Payment type", store=True, readonly=False, compute="_compute_card_payment_type"
    )
    number_months = fields.Selection(
        selection=[
        ('0', '0'),
        ('3', '3'),
        ('6', '6'),
        ('9', '9'),
        ('12', '12'),
        ('18', '18'),
        ('24', '24'),
        ('36', '36'),
        ('48', '48'),
        ('60', '60'),
        ],
        string="Number of months", store=True, readonly=False, compute="_compute_nmero_de_meses"
    )
    number_lot = fields.Char(store=True, readonly=False, compute="_compute_number_lot")
    authorization_number = fields.Char(string="Authorization number")
    bank_id = fields.Many2one("res.partner.bank")
        