
from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sales_amount_report_uafe = fields.Monetary(
        related='company_id.sales_amount_report_uafe',
        string='Sales amount reported by UAFE', readonly=False,
        help='We specify the amount that customer purchases must reach to be considered in the UAFE report.')