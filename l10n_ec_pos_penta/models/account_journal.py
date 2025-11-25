# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _


class AccountJournal(models.Model):
    _inherit = 'account.journal'
    
    cashbox_id = fields.Many2one('cash.box', string="Cash Box", tracking=True)