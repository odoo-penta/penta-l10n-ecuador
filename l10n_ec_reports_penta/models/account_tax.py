# -*- coding: utf-8 -*-
from odoo import fields, models, _


class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'

    show_report = fields.Boolean(default=False, help="If this tax group is checked, it will be considered in the A1 sales report.")
    report_name = fields.Char()
    type_ret = fields.Selection(
        [
            ('withholding_iva_purchase', 'Withholding iva purchase'),
            ('withholding_iva_sales', 'Withholding iva sales'),
            ('withholding_rent_purchase', 'Withholding rent purchase'),
            ('withholding_rent_sales', 'Withholding rent sales'),
        ], default=False)
