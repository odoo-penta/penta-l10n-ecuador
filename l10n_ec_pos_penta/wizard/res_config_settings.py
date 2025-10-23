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
        config_parameter='l10n_ec_pos_pentacash_imbalance_limit',
    )
