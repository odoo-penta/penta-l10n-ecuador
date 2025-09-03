# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountCards(models.Model):
    _name = 'account.cards'
    _description = 'Tarjetas de Crédito'

    name = fields.Char(string="Nombre de la Tarjeta", required=True)
    active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)

class PosPayment(models.Model):
    _inherit = 'account.payment'

    batch_number = fields.Char(string='Número de Lote')
    reference_number = fields.Char(string='Referencia')
    authorization_number = fields.Char(string='Número de Autorización')
    credit_card_type_id = fields.Many2one('account.cards', string='Tipo de Tarjeta')