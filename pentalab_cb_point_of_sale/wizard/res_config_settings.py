# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)
from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    # Config params
    cash_imbalance_limit = fields.Float(
        string="Cash Imbalance Limit",
        help="The maximum amount of cash imbalance allowed before a warning is raised.",
        config_parameter='pentalab_cb_point_of_sale.cash_imbalance_limit',
    )
    allow_credit_note_cash = fields.Boolean(
        string="Allow credit note",
        help="If checked, it allows the generation of credit notes for invoices in the cash register sessions.",
        config_parameter="pentalab_cb_point_of_sale.allow_credit_note_cash"
    )
    allow_advance_cash = fields.Boolean(
        string="Allow advance",
        help="If checked, allows the use of advances for invoices in cashier sessions.",
        config_parameter="pentalab_cb_point_of_sale.allow_advance_cash"
    )