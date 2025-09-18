# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    
    journal_type = fields.Selection(related='journal_id.payment_info_type', readonly=True, string="Journal Type")
    bank_reference = fields.Char(string="Bank reference")
    used_card_id = fields.Many2one(
        'account.cards',
        string='Tarjeta usada',
        domain=[('active', '=', True)],
        ondelete='restrict',
        index=True,
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
    show_ref = fields.Boolean(compute="_compute_visibility_flags", store=False)
    show_bank_cc = fields.Boolean(compute="_compute_visibility_flags", store=False)  # bank_id en card o check
    show_card = fields.Boolean(compute="_compute_visibility_flags", store=False)     # resto solo en card
    
    issuing_entity = fields.Char(string="Entidad emisora")
    show_issuing_entity = fields.Boolean(compute="_compute_show_issuing_entity", store=False)

    @api.depends('journal_type')
    def _compute_visibility_flags(self):
        for rec in self:
            rec.show_ref = False
            rec.show_bank_cc = False
            rec.show_card = False
            if rec.journal_type:
                ptype = rec.journal_type or False
                rec.show_ref = ptype in ('bank', 'check')
                rec.show_bank_cc = ptype in ('card', 'check')
                rec.show_card = (ptype == 'card')

    @api.depends('payment_type')
    def _compute_show_issuing_entity(self):
        for rec in self:
            rec.show_issuing_entity = (rec.payment_type == 'inbound')