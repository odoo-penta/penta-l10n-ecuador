# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

def _entitlement_for_year_index(n_idx: int) -> int:
    """
    n_idx = 1 -> primer año desde date_start
    1..5 => 15 días
    >=6  => 15 + (n_idx - 5) hasta máx 30
    """
    base = 15
    extra = max(0, n_idx - 5)
    return min(base + extra, 30)

class HrContract(models.Model):
    _inherit = "hr.contract"

    vacation_balance_ids = fields.One2many(
        "l10n_ec.ptb.vacation.balance", "contract_id", string="Saldos de Vacaciones",
        help="Resumen por período (año laboral) del contrato."
    )
    vac_total_entitled = fields.Float(
        compute="_compute_vacation_totals", string="Vacaciones acreditadas (total)", store=False
    )
    vac_total_taken = fields.Float(
        compute="_compute_vacation_totals", string="Vacaciones tomadas (total)", store=False
    )
    vac_total_available = fields.Float(
        compute="_compute_vacation_totals", string="Vacaciones disponibles (total)", store=False
    )

    @api.depends("vacation_balance_ids.days_entitled",
                 "vacation_balance_ids.days_taken")
    def _compute_vacation_totals(self):
        for rec in self:
            entitled = sum(rec.vacation_balance_ids.mapped("days_entitled"))
            taken = sum(rec.vacation_balance_ids.mapped("days_taken"))
            rec.vac_total_entitled = entitled
            rec.vac_total_taken = taken
            rec.vac_total_available = max(entitled - taken, 0.0)

    # --- Generación/actualización de periodos de vacaciones del contrato ---
    def _ensure_vacation_balances(self):
        """
        Genera/actualiza saldos por cada año laboral cumplido desde date_start.
        Período i: [date_start + (i-1) años, date_start + i años)
        """
        for rec in self:
            if not rec.date_start:
                continue

            # límite superior: si el contrato terminó, hasta esa fecha; si no, hasta hoy
            today = fields.Date.context_today(rec)
            end_anchor = rec.date_end or today
            # años completos transcurridos (si el día/mes del aniversario no ha llegado, no genera el siguiente)
            years = relativedelta(end_anchor, rec.date_start).years
            if years < 1:
                continue

            Balance = self.env["l10n_ec.ptb.vacation.balance"]
            existing = Balance.search([("contract_id", "=", rec.id)])
            existing_map = {b.year_index: b for b in existing}

            for idx in range(1, years + 1):
                period_start = rec.date_start + relativedelta(years=idx - 1)
                period_end = rec.date_start + relativedelta(years=idx)
                entitled = _entitlement_for_year_index(idx)

                bal = existing_map.get(idx)
                if bal:
                    # actualizar fechas y días acreditados (no toca lo tomado)
                    bal.write({
                        "period_start": period_start,
                        "period_end": period_end,
                        "days_entitled": entitled,
                    })
                else:
                    Balance.create({
                        "contract_id": rec.id,
                        "year_index": idx,
                        "period_start": period_start,
                        "period_end": period_end,
                        "days_entitled": entitled,
                    })

    # hook útil al abrir formulario/guardar/cron
    @api.onchange("date_start", "date_end")
    def _onchange_dates_generate_balances(self):
        self._ensure_vacation_balances()

    def write(self, vals):
        res = super().write(vals)
        if {"date_start", "date_end"} & set(vals.keys()):
            self._ensure_vacation_balances()
        return res

    def action_rebuild_vacation_balances(self):
        """Botón opcional para recalcular todo."""
        self._ensure_vacation_balances()
        return True
