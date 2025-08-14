# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import fields, models

def _first_day_this_month():
    today = fields.Date.context_today(None)
    # today viene como string o date según contexto; normalizamos:
    if isinstance(today, str):
        today = fields.Date.from_string(today)
    return today.replace(day=1)

def _last_day_this_month():
    d = _first_day_this_month()
    last = d + relativedelta(months=1, days=-1)
    return last

class PentalabInvoiceReportWizard(models.TransientModel):
    _name = "pentalab.invoice.report.wizard"
    _description = "Parámetros - Anexo de Compras"

    date_from = fields.Date("Desde", default=_first_day_this_month)
    date_to = fields.Date("Hasta", default=_last_day_this_month)
    journal_ids = fields.Many2many(
        "account.journal",
        string="Diarios",
        domain="[('type','=','purchase')]",
        help="Seleccione uno o varios diarios de Compras"
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
        return {
            "type": "ir.actions.act_window",
            "name": "Anexo de Compras",
            "res_model": "pentalab.invoice.report.line",
            "view_mode": "list",
            "views": [(self.env.ref("pentalab_report.view_pentalab_invoice_report_line_list").id, "list")],
            "target": "current",
            "domain": self._domain(),
        }
