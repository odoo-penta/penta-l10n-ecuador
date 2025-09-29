# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import api, models

class ReportCashClosing(models.AbstractModel):
    _name = 'report.l10n_ec_point_of_sale.report_cash_closing_template'
    _description = 'Cash Closing Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        session = self.env['cash.box.session'].browse(docids)
        user = self.env.user
        return {
            'doc_ids': docids,
            'doc_model': 'cash.box.session',
            'docs': session,
            'payment_summary': session._get_payment_summary(),
            'user_name': user.name,
            'user_identification': user.partner_id.vat or '',
        }
