# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'
    
    def _create_invoices(self, sale_orders):
        res = super()._create_invoices(sale_orders)
        for order in sale_orders:
            invoice = res.filtered(lambda inv: inv.invoice_origin == order.name)
            if len(invoice) == 1:
                invoice.write({
                    'entry_percentage': order.entry_percentage,
                    'risk_percentage': order.risk_percentage,
                    'interest': order.interest,
                    'month_interest': order.month_interest,
                    'apply_interest_grace': order.apply_interest_grace,
                    'proration': order.proration,
                    'months_of_grace': order.months_of_grace,
                    'minimum_fee': order.minimum_fee,
                    'payment_period': order.payment_period,
                    'factor_to_apply': order.factor_to_apply,
                    'financing_amount': order.financing_amount,
                    'total_interest_amount': order.total_interest_amount,
                })
                line_deferred_vals = []
                for line in order.line_deferred_ids:
                    line_deferred_vals.append(fields.Command.create({
                        'month': line.month,
                        'initial_balance': line.initial_balance,
                        'interest_amount': line.interest_amount,
                        'amortization': line.amortization,
                        'additional_grace_interest': line.additional_grace_interest,
                        'final_balance': line.final_balance,
                        'fixed_fee': line.fixed_fee,
                        'due_date': line.due_date,
                    }))
                invoice.write({'line_deferred_ids': line_deferred_vals})
        return res
