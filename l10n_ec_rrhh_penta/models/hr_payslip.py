# -*- coding: utf-8 -*-
from odoo import models
from odoo.tools import float_is_zero


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
    
    def _prepare_slip_lines(self, date, line_ids):
        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Payroll')
        new_lines = []
        for line in self.line_ids.filtered(lambda line: line.category_id):
            amount = line.total
            if line.code == 'NET': # Check if the line is the 'Net Salary'.
                for tmp_line in self.line_ids.filtered(lambda line: line.category_id):
                    if tmp_line.salary_rule_id.not_computed_in_net: # Check if the rule must be computed in the 'Net Salary' or not.
                        if amount > 0:
                            amount -= abs(tmp_line.total)
                        elif amount < 0:
                            amount += abs(tmp_line.total)
            if float_is_zero(amount, precision_digits=precision):
                continue
            
            debit_account_id = line.salary_rule_id.account_debit.id
            credit_account_id = line.salary_rule_id.account_credit.id
            # Considerar la sección contable del contrato
            section = self._get_contract_section()
            if section:
                rule_lines = line.salary_rule_id.account_section_line_ids.filtered(
                    lambda l: l.section_id.id == section.id
                )
                if rule_lines:
                    if not debit_account_id:
                        debit_account_id = rule_lines[0].account_debit_id.id
                    if not credit_account_id:
                        credit_account_id = rule_lines[0].account_credit_id.id
            
            if debit_account_id: # If the rule has a debit account.
                debit = amount if amount > 0.0 else 0.0
                credit = -amount if amount < 0.0 else 0.0

                debit_line = next(self._get_existing_lines(
                    line_ids + new_lines, line, debit_account_id, debit, credit), False)

                if not debit_line:
                    debit_line = self._prepare_line_values(line, debit_account_id, date, debit, credit)
                    debit_line['tax_ids'] = [(4, tax_id) for tax_id in line.salary_rule_id.account_debit.tax_ids.ids]
                    new_lines.append(debit_line)
                else:
                    debit_line['debit'] += debit
                    debit_line['credit'] += credit

            if credit_account_id: # If the rule has a credit account.
                debit = -amount if amount < 0.0 else 0.0
                credit = amount if amount > 0.0 else 0.0
                credit_line = next(self._get_existing_lines(
                    line_ids + new_lines, line, credit_account_id, debit, credit), False)

                if not credit_line:
                    credit_line = self._prepare_line_values(line, credit_account_id, date, debit, credit)
                    credit_line['tax_ids'] = [(4, tax_id) for tax_id in line.salary_rule_id.account_credit.tax_ids.ids]
                    new_lines.append(credit_line)
                else:
                    credit_line['debit'] += debit
                    credit_line['credit'] += credit
        return new_lines
