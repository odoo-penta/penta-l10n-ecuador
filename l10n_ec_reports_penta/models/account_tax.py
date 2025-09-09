# -*- coding: utf-8 -*-
from odoo import fields, models, _


class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'

    show_report_a1 = fields.Boolean(default=False, help="If this tax group is checked, it will be considered in the A1 sales report.")
    report_a1_name = fields.Char()
