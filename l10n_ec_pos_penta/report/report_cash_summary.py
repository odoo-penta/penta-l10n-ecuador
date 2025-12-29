# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import api, models

class ReportCashSummary(models.AbstractModel):
    _name = 'report.l10n_ec_pos_penta.report_cash_summary_template'
    _description = 'Cash Summary Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        session = self.env['cash.box.session'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'cash.box.session',
            'docs': session,
            'payment_summary': session._get_payment_summary(),
            'journal_payment_summary': session.get_payment_summary_by_journal(),
            'payments': session._get_payments(),
            'invoices': session._get_invoices(),
            'deposit': session.deposit_id,
        }
