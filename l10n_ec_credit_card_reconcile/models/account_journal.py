# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    account_commission = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta comisiones'
    )
    
    reference_contact_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contacto de Referencia'
    )
