# -*- coding: utf-8 -*-
from odoo import fields, models

class VacationMove(models.Model):
    _name = "l10n_ec.ptb.vacation.move"
    _description = "Movimiento de vacaciones (aplicación/reversión por permiso)"
    _order = "id"

    balance_id = fields.Many2one("l10n_ec.ptb.vacation.balance", required=True, ondelete="cascade")
    leave_id = fields.Many2one("hr.leave", required=True, ondelete="cascade")
    days = fields.Float(string="Días", required=True)
    state = fields.Selection([("done", "Aplicado"), ("cancel", "Revertido")], default="done", required=True)
