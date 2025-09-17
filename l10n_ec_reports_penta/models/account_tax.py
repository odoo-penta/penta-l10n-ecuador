# -*- coding: utf-8 -*-
from odoo import fields, models, _


class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'

    show_report = fields.Boolean(default=False, help="If this tax group is checked, it will be considered in the A1 sales report.")
    report_name = fields.Char()
    type_ret = fields.Selection(
        [
            ('withholding_iva_purchase', 'Retencion IVA Compras'),
            ('withholding_iva_sales', 'Retencion IVA Ventas'),
            ('withholding_rent_purchase', 'Retencion Renta Compras'),
            ('withholding_rent_sales', 'Retencion Renta Ventas'),
        ], default=False)
