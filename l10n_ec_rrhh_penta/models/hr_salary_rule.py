# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    account_section_id = fields.Many2one(
        "hr.account.section",
        string="Sección contable",
        help="Seleccione la sección contable; las cuentas se precargarán desde la sección.",
    )
    account_section_line_ids = fields.One2many(
        'hr.salary.rule.account.section.line',
        'rule_id',
        string='Cuentas por Sección'
    )

  
    @api.constrains("account_section_id", "account_debit", "account_credit")
    def _check_accounts_if_section(self):
       
        for rule in self:
            if rule.account_section_id and (not rule.account_debit or not rule.account_credit):
                raise ValidationError(_(
                    "La regla salarial ‘%s’ tiene una Sección contable, "
                    "pero no tiene configuradas la Cuenta Débito y/o Cuenta Crédito.",
                    rule.name or "",
                ))

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        for rule in rules:
            rule._ensure_all_sections_lines()
        return rules



    def action_sync_account_sections(self):
        """Crear líneas faltantes con todas las secciones contables activas"""
        sections = self.env["hr.account.section"].search([("active", "=", True)])
        for rule in self:
            existing_sections = rule.account_section_line_ids.mapped("section_id.id")
            to_create = [
                {"rule_id": rule.id, "section_id": s.id}
                for s in sections if s.id not in existing_sections
            ]
            if to_create:
                self.env["hr.salary.rule.account.section.line"].create(to_create)

    def _ensure_all_sections_lines(self):
        """Crea líneas vacías de mapeo por cada sección contable (si no existen).
        Útil para que el usuario vea TODAS las secciones al abrir la regla.
        """
        Section = self.env["hr.account.section"]
        for rule in self:
            existing_sections = set(rule.account_section_line_ids.mapped("section_id").ids)
            for section in Section.search([]):
                if section.id not in existing_sections:
                    self.env["hr.salary.rule.account.section.line"].create({
                        "rule_id": rule.id,
                        "section_id": section.id,
                        # cuentas quedan vacías para que el contador las asigne
                    })
                    
