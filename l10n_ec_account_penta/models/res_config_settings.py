# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    asset_template_id = fields.Many2one(
        related='company_id.asset_template_id',
        config_parameter='l10n_ec_account_penta.asset_template_id',
        company_dependent=True,
        string='Assets template report minute', readonly=False,
        help='We configured the default template to be used for asset records.')
    advanced_payments = fields.Boolean(
        related='company_id.advanced_payments',
        config_parameter='l10n_ec_account_penta.advanced_payments',
        company_dependent=True,
        string='Advanced Payments', readonly=False,
        help='If enabled, enables advanced payment management.')
