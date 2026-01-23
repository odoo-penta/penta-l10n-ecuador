# -*- coding: utf-8 -*-
from datetime import date,timedelta
from odoo import api,fields, models, _
from odoo.exceptions import ValidationError


class HrLeave(models.Model):
    _inherit = "hr.leave"
    
    is_vacation_selected = fields.Boolean(
        string="¿Tipo Vacaciones?",
        compute="_compute_is_vacation_selected",
        store=False
    )
    # Indicadores visibles en el form (solo lectura)
    vacation_available = fields.Float(string="Vacaciones disponibles", compute="_compute_vacation_counters", store=False)
    vacation_taken = fields.Float(string="Vacaciones tomadas", compute="_compute_vacation_counters", store=False)
    vacation_remaining = fields.Float(string="Vacaciones restantes", compute="_compute_vacation_counters", store=False)

    @api.depends('holiday_status_id')
    def _compute_is_vacation_selected(self):
        for leave in self:
            # TRUE Si tiene tipo de permiso y el tipo de permiso es de vacaciones
            leave.is_vacation_selected = bool(leave.holiday_status_id and getattr(leave.holiday_status_id, 'is_vacation', False))

    @api.depends('employee_id', 'holiday_status_id', 'date_from', 'date_to')
    def _compute_vacation_counters(self):
        # Dia actual
        today = date.today()
        for leave in self:
            # Setear valores en cero
            leave.vacation_available = leave.vacation_taken = leave.vacation_remaining = 0.0
            # Pasar logica si no tiene empleado o no es vacaciones
            if not leave.employee_id or not leave.is_vacation_selected:
                continue
            # Obtener contrato activo
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', leave.employee_id.id),
                ('active', '=', True),
                ('date_start', '<=', today),
                '|', ('date_end', '=', False), ('date_end', '>=', today),
            ], order='date_start desc', limit=1)
            # Pasar si no tiene contrato
            if not contract:
                continue
            # Obtener dias de vacaciones disponibles en el contrato
            total_disponibles = float(getattr(contract, 'vac_total_available', 0.0))
            # Tiempo aprobado de tipo vacaciones en el rango del contrato
            dom_leaves = [
                ('employee_id', '=', leave.employee_id.id),
                ('state', 'in', ('validate', 'validate1')),
                ('holiday_status_id.is_vacation', '=', True),
            ]
            if contract.date_start:
                dom_leaves.append(('request_date_from', '>=', contract.date_start))
            if contract.date_end:
                dom_leaves.append(('request_date_to', '<=', contract.date_end))
            # Obtener vacaciones tomadas
            leaves_taken = self.env['hr.leave'].search(dom_leaves)
            total_tomadas = sum(leaves_taken.mapped('number_of_days')) if leaves_taken else 0.0
            # Obtener vacaciones restantes
            restantes = max(total_disponibles - total_tomadas, 0.0)
            # Asignar valores
            leave.vacation_available = total_disponibles
            leave.vacation_taken = total_tomadas
            leave.vacation_remaining = restantes

    @api.onchange('holiday_status_id', 'date_from', 'date_to', 'number_of_days', 'employee_id')
    def _onchange_block_exceeding_vacation(self):
        """Evita que soliciten más días de los restantes (solo cuando es Vacaciones)."""
        for leave in self:
            if not leave.is_vacation_selected:
                continue
            leave._compute_vacation_counters()
            # number_of_days puede ser float; 
            if leave.number_of_days and leave.vacation_remaining and (leave.number_of_days > leave.vacation_remaining):
                # Mensaje, no rompe UI 
                return {
                    'warning': {
                        'title': "Vacaciones insuficientes",
                        'message': (
                            f"Estás solicitando {r.number_of_days:.2f} días y solo tienes "
                            f"{r.vacation_remaining:.2f} días restantes."
                        ),
                    }
                }

    @api.constrains('state', 'holiday_status_id', 'number_of_days', 'employee_id')
    def _check_vacation_not_exceeding_on_approve(self):
        """Bloquea en validación (seguridad del lado servidor) pedir > restantes."""
        for leave in self:
            if leave.is_vacation_selected and leave.state in ('validate', 'validate1'):
                leave._compute_vacation_counters()
                if leave.number_of_days > (leave.vacation_remaining + leave.number_of_days_taken_by_this_request()):
                    # nota: number_of_days_taken_by_this_request() es opcional 
                    # descontar en “tomadas”;
                    if leave.number_of_days > leave.vacation_remaining:
                        raise ValidationError(
                            f"No puedes aprobar {leave.number_of_days:.2f} días. "
                            f"El empleado tiene {leave.vacation_remaining:.2f} días restantes."
                        )

    def _get_requested_days(self):
        self.ensure_one()
        return abs(self.number_of_days or 0.0)

    # --- VALIDACIÓN:---
    @api.constrains("holiday_status_id", "employee_id", "date_from", "date_to", "number_of_days")
    def _check_vacation_available(self):
        for rec in self:
            lt = rec.holiday_status_id
            if not lt or not lt.is_vacation or not rec.employee_id or rec.state in ("refuse", "cancel"):
                continue
            contract = rec.employee_id.contract_id
            if not contract:
                continue
            # asegurar saldos al día
            contract._ensure_vacation_balances()
            requested = rec._get_requested_days()
            available_total = contract.vac_total_available
            if requested > (available_total + 1e-6):
                raise ValidationError(_("No puede solicitar %s día(s). Disponibles en contrato: %s") % (requested, available_total))

    # --- APLICACIÓN AL APROBAR ---
    def action_approve(self):
        res = super().action_approve()
        for rec in self.filtered(lambda l: l.holiday_status_id.is_vacation and l.state == "validate"):
            contract = rec.employee_id.contract_id
            if not contract:
                continue
            contract._ensure_vacation_balances()
            remaining = rec._get_requested_days()
            # consumir desde el período más antiguo con saldo
            balances = contract.vacation_balance_ids.sorted("year_index")
            Move = self.env["l10n_ec.ptb.vacation.move"]
            for bal in balances:
                if remaining <= 0:
                    break
                take = min(bal.days_available, remaining)
                if take > 0:
                    Move.create({
                        "balance_id": bal.id,
                        "leave_id": rec.id,
                        "days": take,
                        "state": "done",
                    })
                    remaining -= take
            if remaining > 1e-6:
                raise ValidationError(_("No se pudo consumir todo el periodo de vacaciones. Faltan %s día(s).") % remaining)
        return res

    # --- REVERSIONES si se rechaza o se cancela ---
    def action_refuse(self):
        res = super().action_refuse()
        self._revert_vacation_moves()
        return res

    def unlink(self):
        self._revert_vacation_moves()
        return super().unlink()

    def _revert_vacation_moves(self):
        moves = self.env["l10n_ec.ptb.vacation.move"].search([("leave_id", "in", self.ids), ("state", "=", "done")])
        for m in moves:
            m.write({"state": "cancel"})
