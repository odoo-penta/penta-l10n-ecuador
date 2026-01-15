# -*- coding: utf-8 -*-
from odoo import api, fields, models

class VacationMove(models.Model):
    _name = "l10n_ec.ptb.vacation.move"
    _description = "Movimiento de vacaciones (consumo/ajuste)"
    _order = "date, id"

    name = fields.Char(string="Descripción")
    balance_id = fields.Many2one("l10n_ec.ptb.vacation.balance", required=True, ondelete="cascade")
    leave_id = fields.Many2one("hr.leave", required=True, ondelete="cascade")
    contract_id = fields.Many2one(related="balance_id.contract_id", store=True, readonly=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    days = fields.Float(string="Días", required=True, help="Positivo = consumo. Negativo = devolución/ajuste a favor.")
    reason = fields.Selection([
        ("leave", "Tiempo personal (vacaciones)"),
        ("adjust", "Ajuste manual"),
    ], default="adjust", required=True)
    state = fields.Selection([
        ("draft", "Borrador"),
        ("done", "Confirmado"),
        ("cancel", "Revertido"),
    ], default="done", required=True)
