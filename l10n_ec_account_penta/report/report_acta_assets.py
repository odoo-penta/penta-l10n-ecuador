# -*- coding: utf-8 -*-
from odoo import models


class ReportActaAssets(models.AbstractModel):
    _name = 'report.l10n_ec_account_penta.report_acta_assets'
    _description = 'Fixed Assets Act Report'

    def _get_report_values(self, docids, data=None):
        """Este método recibe el `data` enviado desde report_action"""
        html = data.get('html') if data else ''
        return {'html': html}
