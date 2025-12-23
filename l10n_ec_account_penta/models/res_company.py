
# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    asset_template_id = fields.Many2one('account.asset.template',
        help='We defined the template to be used for the fixed assets report.')
    advanced_payments = fields.Boolean(string='Advanced Payments',
        help='If enabled, enables advanced payment management.')