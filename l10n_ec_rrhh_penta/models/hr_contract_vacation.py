# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

def _entitlement_for_year_index(n_idx: int) -> int:
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

    @api.depends("vacation_balance_ids.days_entitled", "vacation_balance_ids.days_taken")
    def _compute_vacation_totals(self):
        for rec in self:
            entitled = sum(rec.vacation_balance_ids.mapped("days_entitled"))
            taken = sum(rec.vacation_balance_ids.mapped("days_taken"))
            rec.vac_total_entitled = entitled
            rec.vac_total_taken = taken
            rec.vac_total_available = max(entitled - taken, 0.0)

    # -------------------------------------------------------------------------
    # Recalcular saldos (ya existente)
    # -------------------------------------------------------------------------
    def _ensure_vacation_balances(self):
        Balance = self.env["l10n_ec.ptb.vacation.balance"]
        for contract in self:
            if not contract.id or not contract.date_start:
                continue

            end_marker = contract.date_end or date.today()
            years = relativedelta(end_marker, contract.date_start).years
            total_periods = max(1, years + 1)

            for idx in range(1, total_periods + 1):
                start_i = contract.date_start + relativedelta(years=idx-1)
                end_i = contract.date_start + relativedelta(years=idx) - relativedelta(days=1)
                if contract.date_end and start_i > contract.date_end:
                    break

                existing = Balance.search([
                    ('contract_id', '=', contract.id),
                    ('year_index', '=', idx),
                ], limit=1)
                if existing:
                    existing.write({
                        'period_start': start_i,
                        'period_end': end_i,
                    })
                    continue

                entitled = _entitlement_for_year_index(idx)
                Balance.create({
                    'contract_id': contract.id,
                    'year_index': idx,
                    'period_start': start_i,
                    'period_end': end_i,
                    'days_entitled': float(entitled),
                })

    # -------------------------------------------------------------------------
    # Nuevo flujo: eliminar todo y recalcular
    # -------------------------------------------------------------------------
    def action_confirm_rebuild_vacation_balances(self):
        """Confirmación desde el wizard: borra y recalcula todo"""
        Balance = self.env["l10n_ec.ptb.vacation.balance"]
        for contract in self:
            # Borrar todos los saldos existentes
            Balance.search([("contract_id", "=", contract.id)]).unlink()
            # Volver a generar
            contract._ensure_vacation_balances()
        return {"type": "ir.actions.act_window_close"}

    def action_rebuild_vacation_balances(self):
        """Abre ventana de confirmación"""
        return {
            "name": _("Recalcular Vacaciones"),
            "type": "ir.actions.act_window",
            "res_model": "hr.contract.rebuild.vacation.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_ids": self.ids},
        }
