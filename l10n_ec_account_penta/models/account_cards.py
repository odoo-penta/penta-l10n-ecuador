# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountCards(models.Model):
    _name = 'account.cards'
    _description = 'Tarjetas de Crédito'

    company_id = fields.Many2one(
        string='Company', 
        comodel_name='res.company', 
        required=True, 
        default=lambda self: self.env.user.company_id
    )
    name = fields.Char(string="Nombre de la Tarjeta", required=True)
    active = fields.Boolean(string="Activo", default=True)