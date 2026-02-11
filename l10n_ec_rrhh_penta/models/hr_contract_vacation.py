# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta
from calendar import monthrange
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
    vacation_balance_mg_ids = fields.One2many(
        "l10n_ec.ptb.vacation.migration", "contract_id", string="Saldos Anteriores de Vacaciones",
        help="Resumen por período (año laboral) del contrato."
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True
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
    vac_total_provisioned = fields.Monetary(
        compute="_compute_vacation_totals", string="Provisionado (total)", store=True, urrency_field="currency_id"
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for vals in vals_list:
            if vals.get('vacation_balance_mg_ids') or vals.get('date_start') or vals.get('date_end'):
                res.action_confirm_rebuild_vacation_balances()
        return res
        
    def write(self, vals):
        res = super().write(vals)
        if vals.get('vacation_balance_mg_ids') or vals.get('date_start') or vals.get('date_end'):
            self.action_confirm_rebuild_vacation_balances()
        return res
    
    @api.depends("vacation_balance_ids.days_entitled", "vacation_balance_ids.days_taken", "vacation_balance_ids.provisional_holidays")
    def _compute_vacation_totals(self):
        for rec in self:
            entitled = sum(rec.vacation_balance_ids.mapped("days_entitled"))
            taken = sum(rec.vacation_balance_ids.mapped("days_taken"))
            provisioned = sum(rec.vacation_balance_ids.mapped("provisional_holidays"))
            rec.vac_total_entitled = entitled
            rec.vac_total_taken = taken
            rec.vac_total_available = max(entitled - taken, 0.0)
            rec.vac_total_provisioned = provisioned

    # -------------------------------------------------------------------------
    # Recalcular saldos (ya existente)
    # -------------------------------------------------------------------------
    def _ensure_vacation_balances(self):
        today = date.today()
        for contract in self:
            # Obtener valores migrados
            migrations = {
                m.year_index: m
                for m in self.env["l10n_ec.ptb.vacation.migration"].search([
                    ("contract_id", "=", contract.id)
                ])
            }
            # Saltar si no hay contrato o fecha de inicio en contrato
            if not contract.id or not contract.date_start:
                continue
            # Calcular número de períodos a generar
            end_marker = contract.date_end or date.today()
            years = relativedelta(end_marker, contract.date_start).years
            total_periods = max(1, years + 1)
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
                total_entitlement = _entitlement_for_year_index(idx)
                monthly_rate = round(total_entitlement / 12, 4)
                days_entitled = 0.0
                days_pending = 0.0
                # Verificar si es el último período
                is_last_period = (
                    idx == total_periods or
                    (contract.date_end and end_i >= contract.date_end)
                )
                if is_last_period:
                    # ----- MESES CERRADOS -----
                    # Último mes cerrado
                    if today.month == 1:
                        last_closed = date(today.year - 1, 12, 31)
                    else:
                        last_closed = date(
                            today.year,
                            today.month - 1,
                            monthrange(today.year, today.month - 1)[1]
                        )
                    # Acreditar meses completos
                    current = start_i
                    while current <= min(last_closed, end_i):
                        first_day_month = date(current.year, current.month, 1)
                        month_start = max(current, date(current.year, current.month, 1))
                        month_end = date(
                            current.year,
                            current.month,
                            monthrange(current.year, current.month)[1]
                        )
                        if month_start < start_i or month_start.day != 1:
                            # mes parcial de inicio
                            days_in_month = (month_end - first_day_month).days + 1
                            worked_days = (month_end - start_i).days + 1
                            credited = monthly_rate * worked_days / days_in_month
                        else:
                            credited = monthly_rate
                        days_entitled += credited
                        current = month_end + relativedelta(days=1)
                    # ----- MES ACTUAL (POR ACREDITAR) ----
                    if today <= end_i:
                        month_start = max(start_i, date(today.year, today.month, 1))
                        month_end = date(
                            today.year,
                            today.month,
                            monthrange(today.year, today.month)[1]
                        )

                        days_in_month = (month_end - month_start).days + 1
                        worked_days = (today - month_start).days + 1

                        days_pending = round(
                            monthly_rate * worked_days / days_in_month, 4
                        )
                        
                        if today.day == monthrange(today.year, today.month)[1]:
                            # FIN DE MES → consolidar
                            days_entitled += days_pending
                            days_pending = 0.0
                        else:
                            # Día normal → pendiente
                            days_pending = round(days_pending, 2)
                else:
                    # Períodos cerrados
                    days_entitled = total_entitlement
                    days_pending = 0.0
                
                balance_line = self.env["l10n_ec.ptb.vacation.balance"].create({
                    'contract_id': contract.id,
                    'year_index': idx,
                    'period_start': start_i,
                    'period_end': end_i,
                    'days_entitled': float(days_entitled),
                    'days_pending': float(days_pending),
                })
                # Aplicar días de arranque si quedan
                migration = migrations.get(idx)
                if migration:
                    balance_line.days_taken += migration.days_taken
                    balance_line.provisional_holidays += migration.provisional_holidays
                """
                if startup_days > 0:
                    # Si los dias son mayores a los acreditados, consumir todo el periodo
                    if startup_days > days_entitled:
                        balance_line.days_taken = days_entitled
                        # Restar los días consumidos de arranque
                        startup_days -= days_entitled
                    else:
                        balance_line.days_taken = startup_days
                        startup_days = 0.0
                # Asignamos monto de aranque si tiene dias disponibles
                if balance_line.days_available > 0.00:
                    balance_line.provisional_holidays = startup_amount
                    startup_amount = 0.0
                """
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
                # Vamos a sumar las provisiones de vacaciones
                rule_prov = self.env.ref('l10n_ec_rrhh_penta.rule_vac_prov')  # XML ID de la regla
                prov_lines = self.env['hr.payslip.line'].search([
                    ('salary_rule_id', '=', rule_prov.id),
                    ('contract_id', '=', contract.id),
                    ('slip_id.state', 'in', ('done', 'paid')),
                    ('slip_id.date_to', '>=', start_i),
                    ('slip_id.date_to', '<=', end_i),
                ])
                balance_line.provisional_holidays += sum(prov_lines.mapped('total'))
                rule_liq = self.env.ref('l10n_ec_rrhh_penta.rule_vacaciones_tomadas')  # XML ID de la regla
                liq_lines = self.env['hr.payslip.line'].search([
                    ('salary_rule_id', '=', rule_liq.id),
                    ('contract_id', '=', contract.id),
                    ('slip_id.state', 'in', ('done', 'paid')),
                    ('slip_id.date_to', '>=', start_i),
                    ('slip_id.date_to', '<=', end_i),
                ])
                balance_line.provisional_holidays -= sum(liq_lines.mapped('total'))
            """
            # Vamos a restar las liquidaciones de vacaciones
            rule_liq = self.env.ref('l10n_ec_rrhh_penta.rule_vacaciones_tomadas')  # XML ID de la regla
            lines = self.env['hr.payslip.line'].search([
                ('salary_rule_id', '=', rule_liq.id),
                ('slip_id.state', 'in', ('done', 'paid')),
            ])
            # Obtener el valor total liquidado
            total_liq = abs(sum(lines.mapped('total')))
            p_lines = self.env["l10n_ec.ptb.vacation.balance"].search([
                ('contract_id', '=', contract.id),
                ('provisional_holidays', '>', 0.00)
            ], order="year_index asc")
            # Recorrer lineas de balance con provision si tenemos valores a liquidar
            if total_liq:
                for p_line in p_lines:
                    p_line.provisional_holidays -= total_liq
            """

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

    def _cron_recalculate_vacation_balances(self):
        contracts = self.search([
            ('state', '=', 'open'),
            ('date_start', '<=', date.today()),
        ])
        for contract in contracts:
            contract.action_confirm_rebuild_vacation_balances()
