# -*- coding: utf-8 -*-
from odoo import api, fields, models

class VacationBalance(models.Model):
    _name = "l10n_ec.ptb.vacation.balance"
    _description = "Saldo de vacaciones por año laboral"
    _order = "contract_id, year_index"

    contract_id = fields.Many2one("hr.contract", string="Archivo Excel a importar", required=True, ondelete="cascade")
    year_index = fields.Integer(string="Index",required=True, help="1 = primer año laboral desde date_start")
    period_start = fields.Date(string="Inicio",required=True)
    period_end = fields.Date(string="Fin",required=True)

    days_entitled = fields.Float(string="Acreditadas", required=True)
    move_ids = fields.One2many("l10n_ec.ptb.vacation.move", "balance_id", string="Movimientos")
    days_taken = fields.Float(compute="_compute_taken", store=False, string="Tomadas")
    days_available = fields.Float(compute="_compute_taken", store=False, string="Disponibles")

    _sql_constraints = [
        ("uniq_contract_year", "unique(contract_id, year_index)", "Ya existe el período de ese año para este contrato."),
    ]

    @api.depends("move_ids.days")
    def _compute_taken(self):
        for rec in self:
            taken = sum(m.days for m in rec.move_ids if m.state == "done")
            rec.days_taken = taken
            rec.days_available = max(rec.days_entitled - taken, 0.0)
