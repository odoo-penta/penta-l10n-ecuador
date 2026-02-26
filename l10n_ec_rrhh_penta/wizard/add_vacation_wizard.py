# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class L10nEcPtbAddVacationWizard(models.TransientModel):
    _name = "l10n_ec.ptb.add.vacation.wizard"
    _description = "Wizard: Ajustar vacaciones"

    contract_id = fields.Many2one("hr.contract", required=True, readonly=True)
    operation = fields.Selection([
        ("add", "Sumar"),
        ("subtract", "Restar"),
    ], string="Operación", required=True, default="add")
    quantity = fields.Integer(string="Cantidad de días", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        contract_id = self.env.context.get("default_contract_id")
        if contract_id:
            res["contract_id"] = contract_id
        return res

    def _get_balances(self, contract_id):
        return self.env["l10n_ec.ptb.vacation.balance"].sudo().search(
            [("contract_id", "=", contract_id)], order="year_index asc"
        )

    def _get_taken(self, balance):
        return sum(balance.move_ids.filtered(lambda m: m.state == "done").mapped("days"))

    def action_confirm(self):
        self.ensure_one()

        if not self.contract_id:
            raise ValidationError("No se detectó contrato en el asistente.")
        if self.quantity is None or self.quantity == 0:
            raise ValidationError("La cantidad debe ser distinta de cero.")
        if self.quantity < 0:
            raise ValidationError("Ingrese un entero positivo y seleccione la operación adecuada.")

        self.contract_id._ensure_vacation_balances()

        Balance = self.env["l10n_ec.ptb.vacation.balance"].sudo()

        if self.operation == "add":
            latest = Balance.search([("contract_id", "=", self.contract_id.id)], order="year_index desc", limit=1)
            if not latest:
                raise ValidationError("No existen períodos de vacaciones para este contrato.")
            self.env["l10n_ec.ptb.vacation.move"].sudo().create({
                "name": "Ajuste manual: devolución de días",
                "balance_id": latest.id,
                "days": -int(self.quantity),  # negativo = devuelve/añade
                "reason": "adjust",
                "state": "done",
            })

        else:  # subtract -> FIFO
            qty = int(self.quantity)
            balances = self._get_balances(self.contract_id.id)
            if not balances:
                raise ValidationError("No existen períodos de vacaciones para este contrato.")

            for bal in balances:
                if qty <= 0:
                    break
                taken = self._get_taken(bal)
                free = bal.days_entitled - taken
                if free <= 0:
                    continue
                consume = min(free, qty)
                self.env["l10n_ec.ptb.vacation.move"].sudo().create({
                    "name": "Ajuste manual: consumo de días",
                    "balance_id": bal.id,
                    "days": float(consume),  # positivo = consumo
                    "reason": "adjust",
                    "state": "done",
                })
                qty -= consume

            if qty > 0:
                raise ValidationError("No hay suficientes días disponibles para restar esa cantidad.")

        # recalcula totales mostrados
        if hasattr(self.contract_id, "_recompute_vacation_totals"):
            self.contract_id._recompute_vacation_totals()

        self.contract_id.message_post(
            body=f"Se realizó un ajuste manual de vacaciones: operación '{self.operation}', cantidad {self.quantity} día(s)."
        )
        return {"type": "ir.actions.act_window_close"}
