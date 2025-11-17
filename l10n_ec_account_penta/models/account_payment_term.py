# -*- coding: utf-8 -*-

from odoo import Command, fields, models, api, _
from odoo.tools import float_round


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'
    
    generate_installments = fields.Boolean(
        'Generate installments', default=False,
        help="Activate automatic quota generation.")
    installments_number = fields.Integer(default=1)
    
    # --- MÉTODO QUE GENERA LAS LÍNEAS ---
    def _generate_installment_lines(self):
        for term in self:
            if not term.generate_installments or term.installments_number <= 0:
                continue
            n = term.installments_number
            base_percent = 100.0 / n
            lines = []
            accumulated = 0.0
            for i in range(1, n + 1):
                # Ajustar porcentaje en la última cuota
                if i == n:
                    percent = 100.0 - accumulated
                else:
                    percent = float_round(base_percent, precision_digits=2)
                    accumulated += percent

                lines.append(Command.create({
                    'value': 'percent',
                    'value_amount': percent,
                    'delay_type': 'days_after',
                    'nb_days': 30 * i,
                }))
            # Asignar líneas generadas
            term.line_ids = [(5, 0, 0)] + lines
            
    @api.model_create_multi
    def create(self, vals):
        res = super().create(vals)
        for record in res:
            if record.generate_installments and record.installments_number:
                record._generate_installment_lines()
        return res

    def write(self, vals):
        res = super().write(vals)
        for term in self:
            if term.generate_installments and ('generate_installments' in vals or 'installments_number' in vals):
                term._generate_installment_lines()
        return res
