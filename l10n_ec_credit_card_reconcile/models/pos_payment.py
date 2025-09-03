# -*- coding: utf-8 -*-
from odoo import models, fields

class PosPayment(models.Model):
    _inherit = 'account.payment'

    batch_number = fields.Char(string='Número de Lote')
    reference_number = fields.Char(string='Referencia')
    authorization_number = fields.Char(string='Número de Autorización')
    credit_card_type_id = fields.Many2one('account.cards', string='Tipo de Tarjeta')