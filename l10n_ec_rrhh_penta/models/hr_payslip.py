# -*- coding: utf-8 -*-
from odoo import models, api


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_contract_section(self):
        """Obtiene la sección contable desde el contrato asociado al payslip."""
        self.ensure_one()
        return self.contract_id.account_section_id

    def _get_payslip_account_move_lines(self):
        """Sobrescribe la creación de líneas contables para usar las cuentas
        según la sección contable del contrato."""
        if hasattr(super(HrPayslip, self), '_get_payslip_account_move_lines'):
            lines = super()._get_payslip_account_move_lines()
            section = self._get_contract_section()
            if not section:
                return lines

            # Creamos un mapa de nombre → regla salarial
            rule_by_name = {}
            for slip_line in self.line_ids:
                key = (slip_line.name or '').strip()[:128]
                rule_by_name[key] = slip_line.salary_rule_id

            for ml in lines:
                rule = rule_by_name.get((ml.get('name') or '').strip()[:128])
                if not rule:
                    continue

                # Busca las cuentas para la sección del contrato
                line = rule.account_section_line_ids.filtered(
                    lambda l: l.section_id == section
                )[:1]
                if not line:
                    continue

                debit_acc = line.account_debit_id or rule.account_debit_id
                credit_acc = line.account_credit_id or rule.account_credit_id

                if ml.get('debit', 0.0) > 0 and debit_acc:
                    ml['account_id'] = debit_acc.id
                elif ml.get('credit', 0.0) > 0 and credit_acc:
                    ml['account_id'] = credit_acc.id
            return lines

        return super()._get_payslip_account_move_lines()

    def _get_move_line_for_slip_line(self, slip_line, amount, partner_id=False):
        """Hook alternativo si tu versión usa este método."""
        if hasattr(super(HrPayslip, self), '_get_move_line_for_slip_line'):
            ml = super()._get_move_line_for_slip_line(slip_line, amount, partner_id=partner_id)
            mls = ml if isinstance(ml, list) else [ml]
            section = self._get_contract_section()
            if section:
                rule = slip_line.salary_rule_id
                line = rule.account_section_line_ids.filtered(
                    lambda l: l.section_id == section
                )[:1]
                if line:
                    debit_acc = line.account_debit_id or rule.account_debit_id
                    credit_acc = line.account_credit_id or rule.account_credit_id
                    for item in mls:
                        if item.get('debit', 0.0) > 0 and debit_acc:
                            item['account_id'] = debit_acc.id
                        elif item.get('credit', 0.0) > 0 and credit_acc:
                            item['account_id'] = credit_acc.id
            return ml
        return super()._get_move_line_for_slip_line(slip_line, amount, partner_id=partner_id)
