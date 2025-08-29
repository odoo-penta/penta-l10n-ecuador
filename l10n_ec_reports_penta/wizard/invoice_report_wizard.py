# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class PentalabInvoiceReportWizard(models.TransientModel):
    _name = "pentalab.invoice.report.wizard"
    _description = "Parámetros - Anexo de Compras"

    # ---- Defaults correctos (reciben self) ----
    @api.model
    def _first_day_this_month(self):
        today = fields.Date.context_today(self)  # date
        return today.replace(day=1)

    @api.model
    def _last_day_this_month(self):
        first = self._first_day_this_month()
        return first + relativedelta(months=1, days=-1)

    # ---- Campos del wizard ----
    date_from = fields.Date(string="Desde", default=_first_day_this_month)
    date_to   = fields.Date(string="Hasta", default=_last_day_this_month)
    journal_ids = fields.Many2many(
        "account.journal",
        string="Diarios",
        domain="[('type','=','purchase')]",   # solo Compras
        help="Seleccione uno o varios diarios de Compras",
    )

    def _domain(self):
        d = []
        if self.date_from:
            d.append(("date", ">=", self.date_from))
        if self.date_to:
            d.append(("date", "<=", self.date_to))
        if self.journal_ids:
            d.append(("journal_id", "in", self.journal_ids.ids))
        return d

    def action_show(self):
        domain = self._domain()
        # conteos útilisimos
        count_user = self.env["pentalab.invoice.report.line"].search_count(domain)
        count_sudo = self.env["pentalab.invoice.report.line"].sudo().search_count(domain)
        _logger.info("PENTALAB: dominio=%s  user=%s  sudo=%s", domain, count_user, count_sudo)

        return {
            "type": "ir.actions.act_window",
            "name": "Anexo de Compras",
            "res_model": "pentalab.invoice.report.line",
            "view_mode": "list",  # Odoo 18: list
            "views": [(self.env.ref("l10n_ec_reports_penta.view_pentalab_invoice_report_line_list").id, "list")],
            "target": "current",
            "domain": self._domain(),
        }
