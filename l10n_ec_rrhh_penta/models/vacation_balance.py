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
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    year_index = fields.Integer(string="Index",required=True, help="1 = primer año laboral desde date_start")
    period_start = fields.Date(string="Inicio",required=True)
    period_end = fields.Date(string="Fin",required=True)
    move_ids = fields.One2many("l10n_ec.ptb.vacation.move", "balance_id", string="Movimientos")
    days_entitled = fields.Float(string="Acreditadas", required=True)
    days_pending = fields.Float(string="Por acreditar", required=True)
    days_taken = fields.Float(string="Tomadas")
    days_available = fields.Float(compute="_compute_days_available", store=False, string="Disponibles")
    provisional_holidays = fields.Monetary(string="Provisionado", currency_field="currency_id")

    def _compute_days_available(self):
        for rec in self:
            rec.days_available = max(rec.days_entitled - rec.days_taken, 0.0)
            
class VacationBalanceMigration(models.Model):
    _name = "l10n_ec.ptb.vacation.migration"
    _description = "Migración de saldos de vacaciones por período"
    _order = "contract_id, year_index"

    _sql_constraints = [
        (
            "uniq_contract_period",
            "unique(contract_id, year_index)",
            "Ya existe un registro de migración para este contrato y período."
        )
    ]
    
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    contract_id = fields.Many2one(
        "hr.contract",
        string="Contrato",
        required=True,
        ondelete="cascade",
        index=True,
    )
    year_index = fields.Integer(
        string="Período (index)",
        required=True,
        help="Ejemplo: 1, 2, 3..."
    )
    balance_id = fields.Many2one(
        "l10n_ec.ptb.vacation.balance",
        compute="_compute_balance_id",
        store=False,
        string="Balance relacionado",
    )
    period_start = fields.Date(
        related="balance_id.period_start",
        string="Inicio",
        store=False,
        readonly=True,
    )
    period_end = fields.Date(
        related="balance_id.period_end",
        string="Fin",
        store=False,
        readonly=True,
    )
    days_taken = fields.Float(
        string="Vacaciones tomadas",
        digits=(16, 4),
    )
    provisional_holidays = fields.Monetary(
        string="Provisionado",
        currency_field="currency_id",
    )
    
    @api.depends("contract_id", "year_index")
    def _compute_balance_id(self):
        for rec in self:
            rec.balance_id = self.env["l10n_ec.ptb.vacation.balance"].search([
                ("contract_id", "=", rec.contract_id.id),
                ("year_index", "=", rec.year_index),
            ], limit=1)
