# -*- coding: utf-8 -*-
from odoo import fields, models

class HrSalaryRuleAccountSectionLine(models.Model):
    _name = "hr.salary.rule.account.section.line"
    _description = "Cuentas por sección contable en regla salarial"
    _order = "section_id"

    rule_id = fields.Many2one(
        "hr.salary.rule",
        string="Regla salarial",
        required=True,
        ondelete="cascade",
    )
    section_id = fields.Many2one(
        "hr.account.section",
        string="Sección contable",
        required=True,
        ondelete="restrict",
    )
    account_debit_id = fields.Many2one(
        "account.account",
        string="Cuenta Débito",
    )
    account_credit_id = fields.Many2one(
        "account.account",
        string="Cuenta Crédito",
    )

    _sql_constraints = [
        ("unique_rule_section",
         "unique(rule_id, section_id)",
         "La combinación de Regla y Sección debe ser única."),
    ]
