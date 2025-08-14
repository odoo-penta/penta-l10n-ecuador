# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import api, models

class ReportCashClosing(models.AbstractModel):
    _name = 'report.report_cash_closing_template.report_cash_closing_template'
    _description = 'Cash Closing Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['cash.box.closed.wizard'].browse(docids)
        user = self.env.user
        return {
            'doc_ids': docids,
            'doc_model': 'cash.box.closed.wizard',
            'docs': wizard,
            'payment_summary': wizard._get_payment_summary(),
            'user_name': user.name,
            'user_identification': user.partner_id.vat or '',
        }
