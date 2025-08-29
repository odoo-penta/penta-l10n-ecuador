
from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    sales_amount_report_uafe = fields.Monetary(
        string='Sales amount reported by UAFE',
        currency_field='currency_id',
        help='We specify the amount that customer purchases must reach to be considered in the UAFE report.')