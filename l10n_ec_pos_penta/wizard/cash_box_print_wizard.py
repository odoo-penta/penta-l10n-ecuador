# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)
from odoo import models, fields


class CashBoxPrintWizard(models.TransientModel):
    _name = 'cash.box.print.wizard'
    _description = 'Cash Box Print Wizard'

    cash_box_session_id = fields.Many2one(
        'cash.box.session',
        string='Cash Box Session',
        required=True,
        readonly=True
    )
    report_type = fields.Selection([
        ('collections', 'Collections'),
        ('collections_closing', 'Collections and Closing'),
        ('billing_credit_note', 'Billing and Credit Notes'),
        ('summary', 'Cash Summary'),
    ], string='Report', required=True, default='collections')
    
    def action_print(self):
        self.ensure_one()
        # Reporte cobros
        if self.report_type == 'collections':
            report = self.env.ref('l10n_ec_pos_penta.action_cash_collection_report')
        # Reporte cobros y cierre
        elif self.report_type == 'collections_closing':
            report = self.env.ref('l10n_ec_pos_penta.action_cash_closing_report')
        # Reporte facturacion y notas de credito
        elif self.report_type == 'billing_credit_note':
            report = self.env.ref('l10n_ec_pos_penta.action_cash_billing_report')
        # Reporte resumen de caja
        elif self.report_type == 'summary':
            report = self.env.ref('l10n_ec_pos_penta.action_cash_summary_report')
        else:
            return False
        return report.report_action(self.cash_box_session_id)

