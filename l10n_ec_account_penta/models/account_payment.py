# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from addons.account_payment.controllers import payment
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
    internal_transfer_pair_id = fields.Many2one(
        'account.payment',
        string='Related Internal Transfer',
        copy=False,
    )

    internal_transfer_pair_count = fields.Integer(
        compute='_compute_internal_transfer_pair_count'
    )
    is_internal_transfer_child = fields.Boolean(copy=False)
    

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
    

    def _compute_internal_transfer_pair_count(self):
        for rec in self:
            rec.internal_transfer_pair_count = 1 if rec.internal_transfer_pair_id else 0

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
        total = sum(self.expense_line_ids.mapped('amount_cash'))
        if self.amount != total:
            for expense_line in self.expense_line_ids:
                expense_line.amount_cash = self.amount


    def action_view_internal_transfer_pair(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Related Internal Transfer',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'res_id': self.internal_transfer_pair_id.id,
            'target': 'current',
        }
                
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
                    'journal_id': payment.journal_id.id,
                    'line_ids': move_lines,
                    'move_type': 'entry',
                }

                move = self.env['account.move'].create(move_vals)
                move.action_post()

                payment.move_id = move.id
                return super(AccountPayment, payment).action_post()
            
            if payment.payment_mode == 'internal' and payment.advanced_payments and payment.partner_type == 'supplier' and not payment.is_internal_transfer_child:
                company = payment.company_id
                transfer_account = company.transfer_account_id

                if not transfer_account:
                    raise ValidationError(_("Configure the Internal Transfer Account in settings."))

                amount = payment.amount

                # ================================
                # PRIMER ASIENTO (PAGO ORIGEN)
                # Banco origen → Cuenta transferencia
                # ================================
                manual_out = self.env.ref('account.account_payment_method_manual_out', raise_if_not_found=False)

                origin_out_line = payment.journal_id.outbound_payment_method_line_ids.filtered(
                    lambda l: l.payment_method_id == manual_out
                )

                if not origin_out_line:
                    raise ValidationError(_("The origin journal does not have Manual Out payment method configured."))
                origin_liquidity_account = origin_out_line.payment_account_id

                move_lines = [
                    # Débito → Cuenta de transferencia interna
                    (0, 0, {
                        'account_id': transfer_account.id,
                        'partner_id': payment.partner_id.id,
                        'name': payment.memo or 'Transferencia interna',
                        'debit': amount,
                        'credit': 0.0,
                        'payment_id': payment.id,
                    }),
                    # Crédito → Banco origen
                    (0, 0, {
                        'account_id': origin_liquidity_account.id,
                        'partner_id': payment.partner_id.id,
                        'name': payment.memo or 'Transferencia interna',
                        'debit': 0.0,
                        'credit': amount,
                        'payment_id': payment.id,
                    }),
                ]

                move_vals = {
                    'date': payment.date,
                    'journal_id': payment.journal_id.id,
                    'line_ids': move_lines,
                    'move_type': 'entry',
                }

                move = self.env['account.move'].create(move_vals)
                move.action_post()

                payment.move_id = move.id

                # ================================
                # SEGUNDO PAGO (AUTOMÁTICO)
                # Cuenta transferencia → Banco destino
                # ================================

                dest_journal = payment.destination_journal
                manual_in = self.env.ref('account.account_payment_method_manual_in', raise_if_not_found=False)

                dest_in_line = payment.destination_journal.inbound_payment_method_line_ids.filtered(
                    lambda l: l.payment_method_id == manual_in
                )

                if not dest_in_line:
                    raise ValidationError(_("The destination journal does not have Manual In payment method configured."))
                dest_liquidity_account = dest_in_line.payment_account_id

                inbound_payment_method = self.env.ref('account.account_payment_method_manual_in')

                incoming_payment_vals = {
                    'payment_type': 'inbound',
                    'partner_type': payment.partner_type,
                    'partner_id': '',
                    'amount': amount,
                    'date': payment.date,
                    'journal_id': dest_journal.id,
                    'payment_method_id': inbound_payment_method.id,
                    'payment_mode': 'internal',
                    'is_internal_transfer_child': True, 
                }

                incoming_payment = self.env['account.payment'].create(incoming_payment_vals)

                # Forzamos sus cuentas contables
                incoming_move_lines = [
                    # Débito → Banco destino
                    (0, 0, {
                        'account_id': dest_liquidity_account.id,
                        'partner_id': payment.partner_id.id,
                        'name': payment.memo or 'Transferencia interna',
                        'debit': amount,
                        'credit': 0.0,
                        'payment_id': incoming_payment.id,
                    }),
                    # Crédito → Cuenta transferencia
                    (0, 0, {
                        'account_id': transfer_account.id,
                        'partner_id': payment.partner_id.id,
                        'name': payment.memo or 'Transferencia interna',
                        'debit': 0.0,
                        'credit': amount,
                        'payment_id': incoming_payment.id,
                    }),
                ]

                incoming_move = self.env['account.move'].create({
                    'date': payment.date,
                    'journal_id': dest_journal.id,
                    'line_ids': incoming_move_lines,
                    'move_type': 'entry',
                })

                incoming_move.action_post()
                incoming_payment.move_id = incoming_move.id
                incoming_payment.action_post()

                payment.internal_transfer_pair_id = incoming_payment.id
                incoming_payment.internal_transfer_pair_id = payment.id
                
                line_origin = move.line_ids.filtered(
                    lambda l: l.account_id == transfer_account and not l.reconciled
                )

                line_dest = incoming_move.line_ids.filtered(
                    lambda l: l.account_id == transfer_account and not l.reconciled
                )

                lines_to_reconcile = (line_origin + line_dest).filtered(
                    lambda l: l.account_id.reconcile and not l.reconciled
                )

                if lines_to_reconcile:
                    lines_to_reconcile.reconcile()

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
