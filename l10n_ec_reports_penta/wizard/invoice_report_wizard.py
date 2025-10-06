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
        #domain="[('type','=','purchase')]",   # solo Compras
        domain="[('type','=','purchase'), ('company_id','in', context.get('allowed_company_ids', []))]",
        help="Seleccione uno o varios diarios de Compras",
    )

    def _domain(self):
        d = []
        # Si tienes date_key en la vista, usa ese; si no, usa 'date' o 'invoice_date'
        d.append(("date", ">=", self.date_from)) if self.date_from else None
        d.append(("date", "<=", self.date_to))   if self.date_to   else None

        # ***** clave: compañías activas *****
        active_company_ids = self.env.companies.ids  # viene de allowed_company_ids en contexto
        if active_company_ids:
            d.append(("company_id", "in", active_company_ids))

        if self.journal_ids:
            d.append(("journal_id", "in", self.journal_ids.ids))
        return d

    def action_show(self):
        domain = self._domain()

        # logs de control
        count_user = self.env["pentalab.invoice.report.line"].search_count(domain)
        count_sudo = self.env["pentalab.invoice.report.line"].sudo().search_count(domain)
        _logger.info("PENTALAB: dominio=%s  user=%s  sudo=%s", domain, count_user, count_sudo)

        # Re-armamos el contexto para la acción destino
        active_company_ids = self.env.companies.ids
        ctx = dict(self.env.context or {})
        ctx["allowed_company_ids"] = active_company_ids
        if len(active_company_ids) == 1:
            # Si el usuario dejó solo 1 activa, forzamos esa compañía en la vista destino
            ctx["force_company"] = active_company_ids[0]

        return {
            "type": "ir.actions.act_window",
            "name": "Anexo de Compras",
            "res_model": "pentalab.invoice.report.line",
            "view_mode": "list",
            "views": [(self.env.ref("pentalab_report.view_pentalab_invoice_report_line_list").id, "list")],
            "target": "current",
            "domain": domain,
            "context": ctx,
        }
