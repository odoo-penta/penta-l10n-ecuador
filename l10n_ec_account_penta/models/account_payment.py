# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    journal_type = fields.Selection(related='journal_id.payment_info_type', readonly=True, string="Journal Type")
    bank_reference = fields.Char(string="Bank reference")
    used_card_id = fields.Many2one(
        'account.cards',
        string='Tarjeta usada',
        domain=[('active', '=', True)],
        ondelete='restrict',
        index=True,
    )
    card_payment_type = fields.Selection(
        selection=[
        ('Débito', 'Débito'),
        ('Corriente', 'Corriente'),
        ('Diferido con interés', 'Diferido con interés'),
        ('Diferido sin interés', 'Diferido sin interés')
        ], string="Payment type", store=True, readonly=False
    )
    number_months = fields.Selection(
        selection=[
        ('0', '0'),
        ('3', '3'),
        ('6', '6'),
        ('9', '9'),
        ('12', '12'),
        ('18', '18'),
        ('24', '24'),
        ('36', '36'),
        ('48', '48'),
        ('60', '60'),
        ],
        string="Number of months", store=True, readonly=False
    )
    number_lot = fields.Char(store=True, readonly=False)
    authorization_number = fields.Char(string="Authorization number")
    bank_id = fields.Many2one("res.bank")
    show_ref = fields.Boolean(compute="_compute_visibility_flags", store=False)
    show_bank_cc = fields.Boolean(compute="_compute_visibility_flags", store=False)  # bank_id en card o check
    show_card = fields.Boolean(compute="_compute_visibility_flags", store=False)     # resto solo en card
    payment_reference = fields.Char(string="Payment reference", readonly=True)
    # batch_registration = fields.Boolean(string="Activate accounts receivable")
    # internal_transfer_cash = fields.Boolean(string="Internal transfer")
    payment_mode = fields.Selection(
    [
        ('standard', 'Standard payment'),
        ('expense', 'Expense distribution'),
        ('internal', 'Internal transfer'),
    ],
        string="Payment mode",
        default='standard',
        required=True,
        store=True
    )
    expense_line_ids = fields.One2many(
        'account.payment.expense.line',
        'payment_id',
        string="Expense lines"
    )
    destination_journal = fields.Many2one(
        'account.journal',
        string="Destination diary"
    )
    advanced_payments = fields.Boolean(
        related='company_id.advanced_payments',
        store=False,
        readonly=True
    )
    difference_expense_amount = fields.Monetary(
        compute="_compute_difference_expense_amount",
        store=True,
        currency_field='currency_id',
    )

    @api.model_create_multi
    def create(self, vals_list):
        from_wizard = (
            self._context.get('active_model') == 'account.move'
            and self._context.get('active_ids')
            and self._context.get('default_payment_type') == 'outbound'
        )
        if from_wizard:
            for record in vals_list:
                if record.get('memo') and record['memo']:
                    record['payment_reference'] = record['memo']
                    record['memo'] = False
        return super().create(vals_list)

    @api.depends('journal_type')
    def _compute_visibility_flags(self):
        for rec in self:
            rec.show_ref = False
            rec.show_bank_cc = False
            rec.show_card = False
            if rec.journal_type:
                ptype = rec.journal_type or False
                rec.show_ref = ptype in ('bank', 'check')
                rec.show_bank_cc = ptype in ('card', 'check')
                rec.show_card = (ptype == 'card')

    @api.depends('amount', 'expense_line_ids.amount_cash')
    def _compute_difference_expense_amount(self):
        for rec in self:
            total = sum(rec.expense_line_ids.mapped('amount_cash'))
            rec.difference_expense_amount = rec.amount - total        
    
    @api.constrains('expense_line_ids', 'amount')
    def _check_expense_lines_total(self):
        for payment in self:
            total_expenses = sum(payment.expense_line_ids.mapped('amount_cash'))
            if total_expenses > payment.amount:
                raise ValidationError(_(
                    "The sum of the expense line amounts (%s) cannot be greater than the payment amount (%s)." 
                    % (total_expenses, payment.amount)
                ))

    @api.onchange('expense_line_ids', 'amount')
    def _onchange_expense_line_amount(self):
        if not self.is_cashbox_deposit:
            return
        total = sum(self.expense_line_ids.mapped('amount_cash'))
        if self.amount != total:
            for expense_line in self.expense_line_ids:
                expense_line.amount_cash = self.amount
                
    def action_post(self):
        """Override para generar el asiento contable específico cuando hay líneas de gastos"""
        for payment in self:
            if payment.payment_mode == 'expense' and payment.advanced_payments:
                if not payment.expense_line_ids:
                    raise ValidationError(_(
                        "You selected Expense payment mode, but no expense lines were found.\n\n"
                        "Please add expense lines or change the Payment Mode to 'Standard'."
                    ))

                total_expenses = sum(payment.expense_line_ids.mapped('amount_cash'))
                if abs(total_expenses - payment.amount) > 0.01:
                    raise ValidationError(_(
                        "The sum of the expense line amounts (%s) must be equal "
                        "to the payment amount (%s)." % (total_expenses, payment.amount)
                    ))
                method_xml = 'account.account_payment_method_manual_out'
                manual_method = self.env.ref(method_xml, raise_if_not_found=False)
                if not manual_method:
                    raise ValidationError(_("There is no manual payment method (OUT) in the system."))

                # Buscar el método manual OUT configurado en el diario
                method_lines = payment.journal_id.outbound_payment_method_line_ids
                method_line = method_lines.filtered(lambda m: m.payment_method_id == manual_method)

                # Esta es la cuenta correcta
                journal_account = method_line.payment_account_id
                if not journal_account:
                    raise ValidationError(_(
                        "The journal '%s' does not have a default account configured." %
                        payment.journal_id.name
                    ))

                move_lines = []
                is_supplier = payment.partner_type == 'supplier'

                # Línea por cada gasto
                for expense_line in payment.expense_line_ids:
                    move_lines.append((0, 0, {
                        'account_id': expense_line.account_id.id,
                        'partner_id': expense_line.partner_id.id,
                        'name': payment.memo or 'Pago de gastos',
                        'debit': expense_line.amount_cash if is_supplier else 0.0,
                        'credit': 0.0 if is_supplier else expense_line.amount_cash,
                        'payment_id': payment.id,
                    }))

                # Línea del banco/caja
                move_lines.append((0, 0, {
                    'account_id': journal_account.id,
                    'partner_id': payment.partner_id.id,
                    'name': payment.memo or 'Pago de gastos',
                    'debit': 0.0 if is_supplier else payment.amount,
                    'credit': payment.amount if is_supplier else 0.0,
                    'payment_id': payment.id,
                }))

                # Crear asiento
                move_vals = {
                    'date': payment.date,
                    'ref': payment.memo or '',
                    'journal_id': payment.journal_id.id,
                    'line_ids': move_lines,
                    'move_type': 'entry',
                }

                move = self.env['account.move'].create(move_vals)
                move.action_post()

                payment.move_id = move.id
                return super(AccountPayment, payment).action_post()
            
            if payment.payment_mode == 'internal' and payment.advanced_payments:
                    
                if not payment.destination_journal:
                    raise ValidationError(_(
                        "You must select a destination journal to perform the internal transfer."
                    ))
                amount = payment.amount
                # ------------------------------------------------------------
                # 1) OBTENER MÉTODOS DE PAGO MANUAL IN / MANUAL OUT
                # ------------------------------------------------------------
                manual_in = self.env.ref('account.account_payment_method_manual_in', raise_if_not_found=False)
                manual_out = self.env.ref('account.account_payment_method_manual_out', raise_if_not_found=False)

                # ------------------------------------------------------------
                # 2) EXTRAER LAS LÍNEAS DE MÉTODOS DEL DIARIO ORIGEN
                # ------------------------------------------------------------
                origin_in_line = payment.journal_id.inbound_payment_method_line_ids.filtered(
                    lambda l: l.payment_method_id == manual_in
                )
                origin_out_line = payment.journal_id.outbound_payment_method_line_ids.filtered(
                    lambda l: l.payment_method_id == manual_out
                )
                dest_in_line = payment.destination_journal.inbound_payment_method_line_ids.filtered(
                    lambda l: l.payment_method_id == manual_in
                )
                dest_out_line = payment.destination_journal.outbound_payment_method_line_ids.filtered(
                    lambda l: l.payment_method_id == manual_out
                )
                if payment.partner_type == 'customer':
                    # CLIENTE: COBRO
                    # Débito = Origen → manual IN
                    # Crédito = Destino → manual OUT
                    debit_account = origin_in_line.payment_account_id
                    credit_account = dest_out_line.payment_account_id

                elif payment.partner_type == 'supplier':
                    # PROVEEDOR: PAGO
                    # Débito = Destino → manual IN
                    # Crédito = Origen → manual OUT
                    debit_account = dest_in_line.payment_account_id
                    credit_account = origin_out_line.payment_account_id

                move_lines = [
                    # Débito
                    (0, 0, {
                        'account_id': debit_account.id,
                        'partner_id': payment.partner_id.id,
                        'name': payment.memo or 'Transferencia interna',
                        'debit': amount,
                        'credit': 0.0,
                        'payment_id': payment.id,
                    }),
                    # Crédito
                    (0, 0, {
                        'account_id': credit_account.id,
                        'partner_id': payment.partner_id.id,
                        'name': payment.memo or 'Transferencia interna',
                        'debit': 0.0,
                        'credit': amount,
                        'payment_id': payment.id,
                    }),
                ]

                move_vals = {
                    'date': payment.date,
                    'ref': payment.memo or '',
                    'journal_id': payment.journal_id.id,
                    'line_ids': move_lines,
                    'move_type': 'entry',
                }

                move = self.env['account.move'].create(move_vals)
                move.action_post()

                payment.move_id = move.id
                return super(AccountPayment, payment).action_post()
                
            return super(AccountPayment, payment).action_post()
        
class AccountPaymentExpenseLine(models.Model):
    _name = 'account.payment.expense.line'
    _description = 'Expense lines in payments'

    payment_id = fields.Many2one(
        'account.payment',
        string="Payment",
        ondelete="cascade",
        required=True
    )

    account_id = fields.Many2one(
        'account.account',
        string="Accounting account",
        required=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string="Contact",
    )

    amount_cash = fields.Monetary(
        string="Amount",
        required=True
    )

    currency_id = fields.Many2one(
        related="payment_id.currency_id",
        store=True
    )

    @api.onchange('payment_id')
    def _onchange_payment_id(self):
        for line in self:
            if not line.partner_id:
                line.partner_id = line.payment_id.partner_id

    @api.constrains('amount_cash')
    def _check_amount_cash(self):
        for rec in self:
            if rec.amount_cash <= 0:
                raise ValidationError(_("The amount must be greater than zero."))
