
# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    asset_template_id = fields.Many2one('account.asset.template',
        help='We specify the amount that customer purchases must reach to be considered in the UAFE report.')