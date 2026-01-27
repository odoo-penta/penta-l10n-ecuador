# -*- coding: utf-8 -*-
from odoo import api, fields, models

class VacationBalance(models.Model):
    _name = "l10n_ec.ptb.vacation.balance"
    _description = "Saldo de vacaciones por año laboral"
    _order = "contract_id, year_index"
    
    _sql_constraints = [
        ("uniq_contract_year", "unique(contract_id, year_index)", "Ya existe el período de ese año para este contrato."),
    ]

    contract_id = fields.Many2one("hr.contract", string="Archivo Excel a importar", required=True, ondelete="cascade")
    year_index = fields.Integer(string="Index",required=True, help="1 = primer año laboral desde date_start")
    period_start = fields.Date(string="Inicio",required=True)
    period_end = fields.Date(string="Fin",required=True)
    move_ids = fields.One2many("l10n_ec.ptb.vacation.move", "balance_id", string="Movimientos")
    days_entitled = fields.Float(string="Acreditadas", required=True)
    days_pending = fields.Float(string="Por acreditar", required=True)
    days_taken = fields.Float(string="Tomadas")
    days_available = fields.Float(compute="_compute_days_available", store=False, string="Disponibles")

    def _compute_days_available(self):
        for rec in self:
            rec.days_available = max(rec.days_entitled - rec.days_taken, 0.0)
