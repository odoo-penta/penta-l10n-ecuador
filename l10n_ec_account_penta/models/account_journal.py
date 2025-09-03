# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AccountJournal(models.Model):
    _inherit = "account.journal"
    
    require_tc_data = fields.Boolean(
        string='Requires card details',
        help='Check if this method requires additional card information'
    )
    require_bank_data = fields.Boolean(
        string='Requires bank details',
        help='Check if this method requires a bank reference'
    )
    require_check_data = fields.Boolean(
        string='Requires check details',
        help='Check if this method requires check information'
    )