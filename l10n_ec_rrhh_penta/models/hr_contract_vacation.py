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
    # Vacaciones de arranque
    startup_vacation_days = fields.Float(
        string="Días de vacaciones gozadas",
        help="Días de vacaciones iniciales ya consumidos al empleado al crearse el contrato.",
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
        for contract in self:
            # Saltar si no hay contrato o fecha de inicio en contrato
            if not contract.id or not contract.date_start:
                continue
            # Calcular número de períodos a generar
            end_marker = contract.date_end or date.today()
            years = relativedelta(end_marker, contract.date_start).years
            total_periods = max(1, years + 1)
            # Obtener días de vacaciones de arranque
            startup_days = contract.startup_vacation_days or 0.0
            # Obtener vacaciones tomadas en el período del contrato
            leaves_days = sum(self.env['hr.leave'].search([
                ('employee_id', '=', contract.employee_id.id),
                ('holiday_status_id.is_vacation', '=', True),
                ('state', 'in', ('validate', 'validate1')),
                ('date_from', '>=', contract.date_start),
            ]).mapped('number_of_days'))
            # Recorrer periodos a crear
            for idx in range(1, total_periods + 1):
                # Obtener fechas de inicio y fin del período
                start_i = contract.date_start + relativedelta(years=idx-1)
                end_i = contract.date_start + relativedelta(years=idx) - relativedelta(days=1)
                # Saltar si la fecha de inicio del período excede la fecha de fin del contrato
                if contract.date_end and start_i > contract.date_end:
                    break
                # Obtener días acreditados para el período
                entitled = _entitlement_for_year_index(idx)
                balance_line = self.env["l10n_ec.ptb.vacation.balance"].create({
                    'contract_id': contract.id,
                    'year_index': idx,
                    'period_start': start_i,
                    'period_end': end_i,
                    'days_entitled': float(entitled),
                })
                # Aplicar días de arranque si quedan
                if startup_days > 0:
                    # Si los dias son mayores a los acreditados, consumir todo el periodo
                    if startup_days > entitled:
                        balance_line.days_taken = entitled
                        # Restar los días consumidos de arranque
                        startup_days -= entitled
                    else:
                        balance_line.days_taken = startup_days
                        startup_days = 0.0

                # Verificamos si aun tiene dias disponibles por consumir en este periodo y tiene vacaciones
                if balance_line.days_available > 0.00 and leaves_days:
                    if leaves_days > balance_line.days_available:
                        # Consumir solo los días disponibles en el periodo
                        balance_line.days_taken += balance_line.days_available
                        # Restar los días consumidos del periodo
                        leaves_days -= balance_line.days_available
                    else:
                        balance_line.days_taken += leaves_days
                        leaves_days = 0.0

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
