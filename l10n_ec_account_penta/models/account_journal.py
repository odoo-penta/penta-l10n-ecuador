# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AccountJournal(models.Model):
    _inherit = "account.journal"
    
    payment_info_type = fields.Selection(
        selection=[
            ('', 'Ninguno'),
            ('card', 'Requires card information'),
            ('check', 'Requires check information'),
            ('bank', 'Requires bank information'),
        ], string='Payment information', default=''
    )