# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from decimal import Decimal, ROUND_HALF_UP
from odoo.tools.float_utils import float_compare, float_round
from collections import defaultdict
from odoo.exceptions import ValidationError


class CashBoxBaseWizard(models.AbstractModel):
    _name = 'cash.box.base.wizard'
    _description = 'Base Cash Box Wizard'
    _abstract = True

    cash_id = fields.Many2one('cash.box', required=True, string="Cash Box")
    session_id = fields.Many2one('cash.box.session', string="Session")
    currency_id = fields.Many2one('res.currency', related='cash_id.currency_id', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    opening_note = fields.Text()
    closing_note = fields.Text()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        cash_id = self.env.context.get('default_cash_id')
        if not cash_id and self.env.context.get('active_id'):
            session = self.env['cash.box.session'].browse(self.env.context.get('active_id'))
            if session.exists():
                cash_id = session.cash_id.id
        if cash_id:
            cash = self.env['cash.box'].browse(cash_id)
            res['cash_id'] = cash.id
        return res
    
    def _create_sale_order(self, values):
        # creamos la orden de venta
        order_id = self.env['sale.order'].create(values)
        # creamos las lineas de orden de venta
        for line in self.product_line_ids:
            if line.product_id:
                sale_line_values = {
                    'order_id': order_id.id,
                    'product_id': line.product_id.id,
                    'product_packaging_id': line.product_packaging_id.id if line.product_packaging_id else False,
                    'product_uom_qty': line.quantity,
                    'price_unit': line.product_id.list_price,
                    'tax_id': [(6, 0, line.product_id.taxes_id.filtered(lambda t: t.type_tax_use == 'sale').ids)],
                }
                self.env['sale.order.line'].create(sale_line_values)
        return order_id
    
    def _valit_sale_order(self, order_id):
        # confirmamos la orden de venta
        if order_id.state in ('draft', 'sent'):
            order_id.action_confirm()
        # si genero ordenes de entrega, las confirmamos, asignamos y validamos
        for picking in order_id.picking_ids:
            if picking.state != 'done':
                picking.action_confirm()
                picking.action_assign()
                picking.button_validate()
    
    def _create_invoice(self, order_id):
        # creamos el asistente con los valores de la orden de venta
        wizard = self.env['sale.advance.payment.inv'].create({
            'advance_payment_method': 'delivered',
            'sale_order_ids': [(6, 0, [order_id.id])],
        })
        # mandamos a crear la factura
        invoice = wizard[0]._create_invoices(order_id)
        if not invoice:
            raise UserError(_("Failed to create invoice from the sale order."))
        if not invoice.l10n_ec_sri_payment_id:
            max_payment = max(self.payment_method_ids, key=lambda r: r.amount, default=False)
            max_advance = max(self.advance_line_ids, key=lambda a: abs(a.amount), default=False)
            # asignamos el metodo de pago de la caja
            if max_payment:
                invoice.l10n_ec_sri_payment_id = max_payment.payment_method_id.l10n_ec_sri_payment_id.id if max_payment else False
            # si no hay pagos tomamos del anticipo
            elif max_advance:
                invoice.l10n_ec_sri_payment_id = max_advance.move_line_id.move_id.l10n_ec_sri_payment_id.id
        if not invoice.l10n_ec_sri_payment_id:
            invoice.l10n_ec_sri_payment_id = self.cash_id.l10n_ec_sri_payment_id.id
        invoice.action_post()
        return invoice
    
    def _create_movement(self, partner_id, amount, type_op, order=None, obj_related=None):
        # creamos un movimiento de 
        values = {
            'session_id': self.session_id.id,
            'partner_id': partner_id,
            'amount': amount,
            'cashier_id': self.env.user.id,
            'order_id': order.id if order else False,
            'operation_type': type_op,
        }
        if type_op in ('invoice', 'quote'):
            values['invoice_id'] = obj_related.id if obj_related else False
        elif type_op == 'refund':
            values['credit_note_id'] = obj_related.id if obj_related else False
        elif type_op == 'payment':
            values['payment_id'] = obj_related.id if obj_related else False
        return self.env['cash.box.session.movement'].create(values)
    
    def _create_payments(self, invoice=None):
        payments = []
        total_products, total_advances, total_payments = self._get_totals()
        remaining_amount = float(total_products - total_advances)
        today = fields.Date.context_today(self)
        for payment_method in self.payment_method_ids:
            if payment_method.amount > 0:
                journal_id = payment_method.payment_method_id.journal_id.id
                amount = payment_method.amount
                if not self._name == 'cash.box.payment.wizard':
                    if self.exceeds_amount and payment_method.amount > remaining_amount:
                        amount = remaining_amount
                        memo = payment_method.bank_reference or _('Payment for %s') % self.cash_id.name
                        values = {
                            'payment_type': 'inbound',
                            'amount': payment_method.amount - remaining_amount,
                            'date': today,
                            'journal_id': journal_id,
                            'partner_id': self.partner_id.id,
                            'memo': memo,
                        }
                        payment = self.env['account.payment'].create(values)
                        payment.action_validate()
                        payment.action_post()
                if invoice:
                    communication = f"{payment_method.bank_reference} - {invoice.name}" if payment_method.bank_reference else invoice.name
                    wizard = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=[invoice.id]).create({
                        'journal_id': journal_id,
                        'amount': amount,
                        'payment_date': today,
                        'communication': communication,
                    })
                    payment = wizard.with_context(self.env.context, force_is_invoice_payment=True)._create_payments()
                    if payment_method.bank_reference:
                        payment.bank_reference = payment_method.bank_reference
                    if payment_method.card:
                        payment.card = payment_method.card.id
                    if payment_method.card_payment_type:
                        payment.card_payment_type = payment_method.card_payment_type
                    if payment_method.number_months:
                        payment.number_months = payment_method.number_months
                    if payment_method.number_lot:
                        payment.number_lot = payment_method.number_lot
                    if payment_method.authorization_number:
                        payment.authorization_number = payment_method.authorization_number
                    if payment_method.bank_id:
                        payment.bank_id = payment_method.bank_id.id
                    payment.action_validate()
                    payment.action_post()
                else:
                    memo = payment_method.bank_reference or _('Payment for %s') % self.cash_id.name
                    values = {
                        'payment_type': 'inbound',
                        'amount': amount,
                        'date': today,
                        'journal_id': journal_id,
                        'partner_id': self.partner_id.id,
                        'memo': memo,
                    }
                    payment = self.env['account.payment'].create(values)
                    payment.action_validate()
                    payment.action_post()
                payments += payment
            else:
                raise UserError(_("The amount for the payment method '%s' must be greater than zero.") % payment_method.payment_method_id.name)
        return payments

                
    def _create_credit_note(self, invoice_id):
        # creamos el asistente de nota de credito
        wizard = self.env['account.move.reversal'].create({
            'move_ids': [(6, 0, [invoice_id.id])],
            'reason': self.reason,
            'journal_id': self.cash_id.journal_id.id,
            'date': fields.Date.context_today(self),
        })
        # ejecutamos el reverso
        return wizard.reverse_moves().get('res_id', False)
    
    def _validate_amounts(self):
        total_products, total_advances, total_payments = self._get_totals()
        if total_products != total_payments:
            raise UserError(_("The total amount of payments must match the total amount of products."))
        
    def _get_totals(self):
        total_products = Decimal("0.0")
        total_advances = Decimal("0.0")
        total_payments = Decimal("0.0")
        # control
        if not self._name == 'cash.box.payment.wizard':
            for product in self.product_line_ids:
                taxes = product.product_id.taxes_id
                total_included = taxes.compute_all(product.product_id.list_price, quantity=product.quantity, product=product.product_id, partner=self.partner_id)['total_included']
                total_products += Decimal(str(abs(total_included))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            for advance in self.advance_line_ids:
                total_advances += Decimal(str(abs(advance.amount))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for payment in self.payment_method_ids:
            total_payments += Decimal(str(abs(payment.amount))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return total_products, total_advances, total_payments
    
class CashBoxPaymentMethodWizard(models.TransientModel):
    _name = 'cash.box.payment.method.wizard'
    _inherit = 'cash.box.base.wizard'
    _description = 'Payment Method Wizard'

    base_id = fields.Many2one('cash.box.base.wizard', string="Cash Box Base")
    sale_id = fields.Many2one('cash.box.sale.wizard', string="Cash Box Sale")
    payment_id = fields.Many2one('cash.box.payment.wizard', string="Payment")
    quote_id = fields.Many2one('cash.box.quotation.wizard', string="Cash Box Quotation")
    payment_method_id = fields.Many2one(
        'cash.payment.method',
        string="Payment Method", required=True,
        domain="[('id', 'in', available_payment_method_ids)]"
    )
    require_tc_data = fields.Boolean(related='payment_method_id.require_tc_data', readonly=True)
    require_bank_data = fields.Boolean(related='payment_method_id.require_bank_data', readonly=True)
    require_check_data = fields.Boolean(related='payment_method_id.require_check_data', readonly=True)
    available_payment_method_ids = fields.Many2many('cash.payment.method', string="Available Payment Methods")
    amount = fields.Monetary(string="Amount", required=True, default=0.0)
    bank_reference = fields.Char(string="Bank Reference", help="Reference for bank payments")
    card = fields.Many2one('finance.card', string="Card")
    card_payment_type = fields.Selection(
        [('debit', 'Debit'),
         ('current', 'Current'),
         ('deferred_with_interest', 'Deferred with interest'),
         ('deferred_without_interest', 'Deferred without interest')], string="Payment type"
    )
    number_months = fields.Integer(string="Number of months")
    number_lot = fields.Char()
    authorization_number = fields.Char(string="Authorization number")
    bank_id = fields.Many2one("res.partner.bank")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        cash = self.env['cash.box'].browse(res.get('cash_id'))
        res['available_payment_method_ids'] = [(6, 0, cash.payment_method_ids.ids)]
        return res
    
    @api.constrains('payment_method_id', 'bank_reference')
    def _check_bank_reference_required(self):
        for rec in self:
            if rec.payment_method_id.require_bank_data and not rec.bank_reference:
                raise UserError(_("You must provide a Bank Reference when the payment method is bank-related (%s)") % rec.payment_method_id.name)

class CashBoxAdvanceLineWizard(models.TransientModel):
    _name = 'cash.box.advance.line.wizard'
    _inherit = 'cash.box.base.wizard'
    _description = 'Customer Advance Line'
    
    wizard_id = fields.Many2one('cash.box.sale.wizard', required=True, ondelete='cascade')
    partner_id = fields.Many2one(related='wizard_id.partner_id', string='Partner', readonly=True)
    account_id = fields.Many2one('account.account', compute="_compute_account")
    move_line_id = fields.Many2one(
        'account.move.line', string='Advance',
        domain="[('account_id','=',account_id),('partner_id','=',partner_id),('move_id.state','=','posted'),('full_reconcile_id','=',False),('amount_residual','<',0),('debit','=',0)]",
        required=True)
    currency_id = fields.Many2one(related='move_line_id.currency_id', readonly=True)
    amount = fields.Monetary(string='Amount', related='move_line_id.amount_residual', readonly=True)
    
    @api.depends('partner_id')
    def _compute_account(self):
        for record in self:
            advance_config = self.env['account.advance.config'].search([], limit=1)
            advance_account = advance_config.advance_account_customer_id if advance_config.advance_account_customer_id else False
            receivable_account = self.partner_id.property_account_receivable_id
            if advance_account:
                record.account_id = advance_account
            elif receivable_account:
                record.account_id = receivable_account

class CashBoxCoinLineWizard(models.TransientModel):
    _name = 'cash.box.coin.line.wizard'
    _description = 'Coin Line for Initial Balance Wizard'

    wizard_id = fields.Many2one('cash.box.coin.wizard', required=True, ondelete='cascade')
    coin_id = fields.Many2one('cash.box.coin', required=True, readonly=True)
    value = fields.Float(related='coin_id.value', readonly=True)
    quantity = fields.Integer(default=0)

class CashBoxCoinWizard(models.TransientModel):
    _name = 'cash.box.coin.wizard'
    _description = 'Select Coins for Balance'
    
    opened_wizard_id = fields.Many2one('cash.box.open.wizard', ondelete='cascade')
    closed_wizard_id = fields.Many2one('cash.box.closed.wizard', ondelete='cascade')
    coin_line_ids = fields.One2many('cash.box.coin.line.wizard', 'wizard_id', string="Coins")

    def action_confirm_coins(self):
        total = sum(line.value * line.quantity for line in self.coin_line_ids)
        # Construcción del detalle
        coin_lines = []
        for line in self.coin_line_ids:
            if line.quantity > 0:
                coin_lines.append(f"{line.coin_id.name} x {line.quantity}")
        detail_text = "\n".join(coin_lines)
        detail_text += f"\nTotal: ${total:.2f}"
        ctx = self.env.context
        if ctx.get('default_opened_wizard_id'):
            wizard = self.env['cash.box.open.wizard'].browse(ctx['default_opened_wizard_id'])
            wizard.initial_balance = total
            wizard.opening_note = detail_text
            return {
                'name': _('Open Cash Box'),
                'type': 'ir.actions.act_window',
                'res_model': 'cash.box.open.wizard',
                'view_mode': 'form',
                'res_id': wizard.id,
                'target': 'new',
            }
        elif ctx.get('default_closed_wizard_id'):
            wizard = self.env['cash.box.closed.wizard'].browse(ctx['default_closed_wizard_id'])
            wizard.final_balance = total
            wizard.closing_note = detail_text
            return {
                'name': _('Closed Cash Box'),
                'type': 'ir.actions.act_window',
                'res_model': 'cash.box.closed.wizard',
                'view_mode': 'form',
                'res_id': wizard.id,
                'target': 'new',
            }

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        lines = []
        for coin in self.env['cash.box.coin'].search([], order='value asc'):
            lines.append((0, 0, {'wizard_id': self.env.context.get('active_id', False),  'coin_id': coin}))
        res['coin_line_ids'] = lines
        return res
    
class CashBoxOpenWizard(models.TransientModel):
    _name = 'cash.box.open.wizard'
    _inherit = 'cash.box.base.wizard'
    _description = 'Open Cash Box Wizard'

    initial_balance = fields.Monetary(string="Initial Balance", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        cash = self.env['cash.box'].browse(res.get('cash_id'))
        last_session = self.env['cash.box.session'].search(
            [('cash_id', '=', cash.id), ('state', '=', 'closed')],
            order="closing_date desc", limit=1
        )
        last_balance = last_session.closing_balance if last_session else 0.0
        res.update({
            'initial_balance': last_balance,
        })
        return res
    
    def action_open_coin_wizard(self):
        # Crear el wizard con líneas
        wizard = self.env['cash.box.coin.wizard'].create({
            'opened_wizard_id': self.id,
            'coin_line_ids': [
                (0, 0, {
                    'coin_id': coin.id,
                    'quantity': 0,
                }) for coin in self.env['cash.box.coin'].search([('currency_id', '=', self.currency_id.id)], order='value asc')
            ]
        })
        return {
            'name': _('Select Coins'),
            'type': 'ir.actions.act_window',
            'res_model': 'cash.box.coin.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_confirm_open(self):
        self.ensure_one()
        # validamos estado
        if self.cash_id.state == 'open':
            raise UserError(_("The cash box is already open."))
        # proceso de apertura
        session = self.cash_id.open_cash(self.initial_balance)
        session.opening_note = self.opening_note
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cash.box.session',
            'res_id': session.id,
            'view_mode': 'form',
            'target': 'current',
        }
        
class CashBoxClosedWizard(models.TransientModel):
    _name = 'cash.box.closed.wizard'
    _inherit = 'cash.box.base.wizard'
    _description = 'Closed Cash Box Wizard'

    final_balance = fields.Monetary(string="Final Balance", required=True)
    suggested_balance = fields.Monetary(readonly=True)
    exceeds_limit = fields.Boolean(string="Exceeds Limit", compute="_compute_exceeds_limit")
    
    @api.depends('final_balance')
    def _compute_exceeds_limit(self):
        limit_amount = float(self.env['ir.config_parameter'].sudo().get_param('l10n_ec_point_of_sale.cash_imbalance_limit'))
        for record in self:
            record.exceeds_limit = False
            if limit_amount > 0.0:
                diff = record.final_balance - record.suggested_balance
                if (diff > 0 and diff >= limit_amount) or (diff < 0 and abs(diff) >= limit_amount):
                    record.exceeds_limit = True

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        cash_id = self.env.context.get('default_cash_id', False)
        if cash_id:
            cash = self.env['cash.box'].browse(cash_id)
            movement_ids = cash.current_session_id.movement_ids
            summary = self._get_payment_summary(movement_ids=movement_ids)
            total_cash = sum(item['cash'] for item in summary.values())
            total_cash += cash.current_session_id.initial_balance
            res['suggested_balance'] = total_cash
        return res
    
    def action_close_coin_wizard(self):
        # Crear el wizard con líneas
        wizard = self.env['cash.box.coin.wizard'].create({
            'closed_wizard_id': self.id,
            'coin_line_ids': [
                (0, 0, {
                    'coin_id': coin.id,
                    'quantity': 0,
                }) for coin in self.env['cash.box.coin'].search([('currency_id', '=', self.currency_id.id)], order='value asc')
            ]
        })
        return {
            'name': _('Select Coins'),
            'type': 'ir.actions.act_window',
            'res_model': 'cash.box.coin.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
        
    @api.onchange('final_balance')
    def _oncahnge_final_balance(self):
        self.closing_note = ''
        
    def applied_diff_closing_balance(self):
        self.ensure_one()
        move_obj = self.env['account.move']
        journal = self.cash_id.close_journal_id
        # Calculo de diferencia
        diff = float_round(self.final_balance - self.suggested_balance, precision_digits=2)
        account_cash = self.cash_id.close_account_id
        if not account_cash:
            raise UserError(_("The journal must have a default account."))
        move_vals = {
            'ref': _('Cash closing adjustment'),
            'journal_id': journal.id,
            'date': fields.Date.context_today(self),
            'line_ids': [],
        }
        if diff > 0:
            # Hay más efectivo del esperado → GANANCIA
            gain_account = self.cash_id.gain_account_id
            move_vals['line_ids'] = [
                (0, 0, {
                    'account_id': account_cash.id,
                    'debit': 0.0,
                    'credit': diff,
                    'name': _('Cash surplus'),
                }),
                (0, 0, {
                    'account_id': gain_account.id,
                    'debit': diff,
                    'credit': 0.0,
                    'name': _('Cash surplus'),
                }),
            ]
        else:
            # Hay menos efectivo del esperado → PÉRDIDA
            loss_account = self.cash_id.loss_account_id
            abs_diff = abs(diff)
            move_vals['line_ids'] = [
                (0, 0, {
                    'account_id': account_cash.id,
                    'debit': abs_diff,
                    'credit': 0.0,
                    'name': _('Cash shortage'),
                }),
                (0, 0, {
                    'account_id': loss_account.id,
                    'debit': 0.0,
                    'credit': abs_diff,
                    'name': _('Cash shortage'),
                }),
            ]
        move = move_obj.create(move_vals)
        move.action_post()
        return move

    def action_confirm_closed(self):
        self.ensure_one()
        # validamos estado
        if self.cash_id.state == 'closed':
            raise UserError(_("The cash box is already closed."))
        self.cash_id.current_session_id.closing_note = self.closing_note
        # asientos de diferencia de cierre
        if self.suggested_balance != self.final_balance:
            diff_move = self.applied_diff_closing_balance()
            self.cash_id.current_session_id.diff_move_id = diff_move.id
        # proceso de cierre
        self.cash_id.closed_cash(self.final_balance)
        # si excede el limite de diferencia, notifica a los administardores de caja
        if self.exceeds_limit:
            for user in self.cash_id.responsible_ids:
                self.env['mail.activity'].create({
                    'res_model_id': self.env['ir.model']._get('cash.box').id,
                    'res_id': self.cash_id.id,
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': 'Revisar exceso de efectivo',
                    'note': f'La caja {self.cash_id.name} se cerró con exceso de diferencia. Por favor, revisa.',
                    'user_id': user.id,
                    'date_deadline': fields.Date.today(),
                })
        
    def print_report(self):
        self.ensure_one()
        return self.env.ref('l10n_ec_point_of_sale.action_cash_closing_report').report_action(self)
    
    def _get_payment_summary(self, movement_ids=None):
        """ Obtiene un resumen de los pagos realizados por movimiento """
        
        def categorize_payment(payment):
            """ Categoriza el pago según su tipo """
            if payment.journal_id.type == 'credit' or payment.journal_id.default_account_id.account_type == 'liability_credit_card':
                return 'card'
            elif payment.journal_id.type == 'bank':
                return 'transfer'
            else:
                return 'cash'
        
        payment_summary = {}
        if not movement_ids:
            movement_ids = self.cash_id.current_session_id.movement_ids
        for movement in movement_ids:
            # instanciamos el diccionario de resumen por movimiento
            summary = {'cash': 0.00, 'transfer': 0.00, 'card': 0.00, 'credit': 0.00}
            # si el movimeinto es factura o cotizacion
            if movement.operation_type in ('invoice', 'quote'):
                # obtenemos los pagos asociados a la factura o cotizacion(factura)
                dict_payments = movement.invoice_id.open_payments()
                payments = self.env['account.payment'].browse(
                    dict_payments.get('res_id') or
                    (dict_payments.get('domain') and dict_payments.get('domain')[0][2]) or
                    []
                ) 
                # iteramos los pagos obtenidos
                for payment in payments:
                    key = categorize_payment(payment)
                    summary[key] += payment.amount
            # si el movimiento es una nota de credito
            elif movement.operation_type == 'refund':
                summary['credit'] += movement.credit_note_id.amount_total
            # si el movimiento es un pago
            else:
                # obtenmos el pago
                payment = movement.payment_id
                key = categorize_payment(payment)
                summary[key] += payment.amount
            payment_summary[movement.id] = summary
        return payment_summary
        
class CashBoxSaleWizard(models.TransientModel):
    _name = 'cash.box.sale.wizard'
    _inherit = 'cash.box.base.wizard'
    _description = 'New Sale Wizard'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    product_line_ids = fields.One2many('cash.box.sale.line.wizard', 'cash_sale_id', string='Products', required=True)
    payment_method_ids = fields.One2many('cash.box.payment.method.wizard', 'sale_id', string="Payment Methods", required=True)
    advance_line_ids = fields.One2many('cash.box.advance.line.wizard', 'wizard_id', string='Advances')
    use_only_advances = fields.Boolean(compute='_compute_use_only_advances')
    has_advance = fields.Boolean(compute='_compute_has_advance')
    exceeds_amount = fields.Boolean(compute="_compute_exceeds_amount")
    
    @api.depends('partner_id')
    def _compute_has_advance(self):
        param = self.env['ir.config_parameter'].sudo().get_param('l10n_ec_point_of_sale.allow_advance_cash')
        for record in self:
            if record.partner_id:
                record.has_advance = param
            else:
                record.has_advance = False
                
    @api.constrains('advance_line_ids')
    def _check_duplicate_advance(self):
        for wizard in self:
            advance_ids = [line.move_line_id.id for line in wizard.advance_line_ids if line.move_line_id]
            if len(advance_ids) != len(set(advance_ids)):
                raise ValidationError(_("You cannot use the same advance more than once."))
    
    @api.depends('advance_line_ids', 'product_line_ids.quantity', 'payment_method_ids.amount')
    def _compute_exceeds_amount(self):
        for wizard in self:
            if wizard.use_only_advances:
                wizard.exceeds_amount = False
                continue
            total_products, total_advances, total_payments = self._get_totals()
            wizard.exceeds_amount = (total_advances + total_payments) > total_products
        
    @api.depends('advance_line_ids', 'product_line_ids')
    def _compute_use_only_advances(self):
        for wizard in self:
            total_products, total_advances, total_payments = self._get_totals()
            wizard.use_only_advances = total_advances >= total_products
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if not self.partner_id:
            self.advance_line_ids = [(5, 0, 0)]
            
    def _validate_amounts(self):
        total_products, total_advances, total_payments = self._get_totals()
        total_paid = total_payments + total_advances
        if total_paid < total_products:
            raise UserError(_("The total amount of payments must match the total amount of products."))
        
    def _apply_selected_advances(self, invoice):
        """
        Aplica automáticamente los anticipos a la factura usando el wizard de conciliación
        sin mostrarlo en la vista (modo silencioso).
        """
        reconciled_ids = []
        for adv in self.advance_line_ids:
            if invoice.amount_residual <= 0:
                break
            outstanding_line = adv.move_line_id
            invoice.js_assign_outstanding_line(outstanding_line.id)
            # Verificar si se conciliaron efectivamente
            if invoice.amount_residual == 0 or outstanding_line.reconciled:
                continue
            # Conciliación forzada (cuentas distintas)
            ctx = {
                'active_model': 'account.move.line',
                'active_ids': [outstanding_line.id, *invoice.line_ids.filtered(lambda l: l.account_id.account_type in ('asset_receivable') and not l.reconciled).ids],
            }
            conciled_wizard = self.env['account.reconcile.wizard'].with_context(**ctx).new({})
            if (conciled_wizard.is_write_off_required or conciled_wizard.force_partials):
                conciled_wizard.allow_partials = True
            conciled_wizard.reconcile()
            reconciled_ids.append(outstanding_line.id)
        return reconciled_ids
    
    def is_immediate_payment_term(self, payment_term):
        if not payment_term:
            return False
        return (
            len(payment_term.line_ids) == 1 and
            payment_term.line_ids[0].nb_days == 0
        )

    def action_confirm(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("You must select an customer."))
        if not self.product_line_ids:
            raise UserError(_("You must add at least one product to the sale."))
        property_payment_term_id = self.partner_id.property_payment_term_id
        if not property_payment_term_id or not self.is_immediate_payment_term(property_payment_term_id):
            if not self.payment_method_ids and not self.advance_line_ids:
                raise UserError(_("You must add at least one payment method."))
            # validamos los montos de los pagos
            self._validate_amounts()
        # completamos los valores de la orden de venta
        order_values = {
            'partner_id': self.partner_id.id,
            'user_id': self.env.user.id,
            'warehouse_id': self.cash_id.warehouse_id.id,
        }
        # creamos la orden de venta
        order = self._create_sale_order(order_values)
        # validamos la orden de venta
        self._valit_sale_order(order)
        # creamos la factura de la orden de venta
        invoice = self._create_invoice(order)
        # consideramos los anticipos si tenemos
        if self.advance_line_ids:
            self._apply_selected_advances(invoice)
        # creamos los pagos asociados a la factura
        if self.payment_method_ids:
            self._create_payments(invoice)
        # creamos el movimiento de sesion
        amount = 0.0
        for pl in self.product_line_ids:
            price_unit = pl.product_id.list_price
            taxes = pl.product_id.taxes_id.compute_all(
                price_unit,
                quantity=pl.quantity,
                product=pl.product_id,
                partner=self.partner_id
            )
            amount += taxes['total_included']
        self._create_movement(
            partner_id = self.partner_id.id,
            amount = amount,
            type_op = 'invoice',
            order = order,
            obj_related = invoice
        )

class CashBoxSaleLineWizard(models.TransientModel):
    _name = 'cash.box.sale.line.wizard'
    _description = 'Cash Box Sale Line Wizard'

    cash_sale_id = fields.Many2one('cash.box.sale.wizard', string='Cash Sale Wizard', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='cash_sale_id.currency_id', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    exist_packaging = fields.Boolean(compute="_compute_exist_packaging", readonly=True)
    product_packaging_id = fields.Many2one('product.packaging', string='Packaging', domain="[('sales', '=', True), ('product_id', '=', product_id)]", check_company=True)
    qty_available = fields.Float('Quantity On Hand', compute='_compute_quantities', readonly=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    price_unit = fields.Float(string='Unit Price', required=True, default=0.0)
    tax_ids = fields.Many2many('account.tax', string='Taxes', domain=[('type_tax_use', '=', 'sale')])
    price_tax = fields.Monetary(string='Tax', compute='_compute_prices', store=True)
    price_total = fields.Monetary(string='Total', compute='_compute_prices', store=True)
    
    @api.depends('product_id')
    def _compute_exist_packaging(self):
        for line in self:
            packaging = self.env['product.packaging'].search([('product_id', '=', line.product_id.id)], limit=1)
            if packaging:
                line.product_packaging_id = packaging.id
                line.exist_packaging = True
            else:
                line.product_packaging_id = False
                line.exist_packaging = False
    
    @api.depends('product_id')
    def _compute_quantities(self):
        ctx = self._context.copy()
        records = self
        for line in records:
            line.qty_available = 0
            if line.product_id:
                # obtenemos el almacen configurado en la caja
                location_id =  line.cash_sale_id.cash_id.warehouse_id.lot_stock_id.id
                ctx['location'] = location_id
                qty_values = line.product_id.with_context(ctx)._compute_quantities_dict(self._context.get('lot_id'),
                                                                                        self._context.get('owner_id'),
                                                                                        self._context.get('package_id'),
                                                                                        self._context.get('from_date'),
                                                                                        self._context.get('to_date'))[line.product_id.id]
                line.qty_available = qty_values['qty_available']
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.quantity = 1.0
            self.price_unit = self.product_id.list_price
            self.tax_ids = [(6, 0, self.product_id.taxes_id.filtered(lambda t: t.type_tax_use == 'sale').ids)]
        else:
            self.quantity = 0.0
            self.price_unit = 0.0
            self.tax_ids = False
    
    @api.depends('tax_ids', 'quantity', 'price_unit')
    def _compute_prices(self):
        for line in self:
            base = line.price_unit * line.quantity
            total_tax = 0.0
            for tax in line.tax_ids:
                if tax.amount_type == 'percent':
                    total_tax += (tax.amount / 100) * base
                elif tax.amount_type == 'fixed':
                    total_tax += tax.amount
            self.price_tax = total_tax
            self.price_total = base + total_tax

class CashBoxCreditNoteWizard(models.TransientModel):
    _name = 'cash.box.credit.note.wizard'
    _inherit = 'cash.box.base.wizard'
    _description = 'Cash Box Credit Note Wizard'

    invoice_ids = fields.Many2many("account.move", 'cash_credit_note_rel', 'wiz_id', 'move_id',
        string="Invoice", required=True,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]")
    reason = fields.Char(string='Reason', required=True, help="Reason for the credit note.")

    def action_confirm(self):
        self.ensure_one()
        if not self.invoice_ids:
            raise UserError(_("You must select an invoice."))
        # recorrremos todas las facturas seleccionadas
        for invoice in self.invoice_ids:
            # creamos la nota de credito
            credit_note = self.env['account.move'].browse(self._create_credit_note(self.invoice_ids))
            credit_note.action_post()
            # creamos el movimiento de caja asociado a la nota de credito
            self._create_movement(
                partner_id = invoice.partner_id.id,
                amount = -invoice.amount_total,
                type_op = 'refund',
                obj_related = credit_note,
            )
        return True
            
class CashBoxPaymentWizard(models.TransientModel):
    _name = 'cash.box.payment.wizard'
    _inherit = 'cash.box.base.wizard'
    _description = 'Cash Box Payment Wizard'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    payment_type = fields.Selection([
        ('outbound', 'Outbound'),
        ('inbound', 'Inbound')
    ], string='Payment Type', required=True, default='inbound')
    payment_method_ids = fields.One2many('cash.box.payment.method.wizard', 'payment_id', string="Payment Methods", required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.payment_method_ids:
            raise UserError(_("The amount must be greater than zero."))
        # creamos los pagos
        payments = self._create_payments()
        # creamos los movimientos
        for payment in payments:
            if self.payment_type == 'inbound':
                payment_amount = payment.amount
            else:
                payment_amount = -payment.amount
            self._create_movement(
                partner_id = self.partner_id.id,
                amount = payment_amount,
                type_op = 'payment',
                obj_related = payment
            )

class CashBoxQuotationWizard(models.TransientModel):
    _name = 'cash.box.quotation.wizard'
    _inherit = 'cash.box.base.wizard'
    _description = 'Cash Box Quotation Wizard'

    sale_order_id = fields.Many2one('sale.order', domain="[('state', 'in', ['draft', 'sale']),('company_id','=',company_id)]", string="Quotations", required=True)
    sale_order_state = fields.Selection(related='sale_order_id.state', depends=['sale_order_id'])
    validated_order = fields.Boolean(readonly=True, compute="_compute_vals_order")
    more_order = fields.Boolean(readonly=True, compute="_compute_vals_order")
    product_line_ids = fields.One2many('cash.box.quotation.line.wizard', 'cash_quotation_id', string='Products', required=True)
    payment_method_ids = fields.One2many('cash.box.payment.method.wizard', 'quote_id', string="Payment Methods", required=True)
    picking_done = fields.Boolean(compute="_compute_picking_done")
    
    @api.depends('sale_order_id')
    def _compute_vals_order(self):
        records = self
        for order in records:
            order.validated_order = False
            order.more_order = False
            if order.sale_order_id and order.sale_order_state == 'sale':
                if len(order.sale_order_id.picking_ids) > 1:
                    order.more_order = True
                for picking in order.sale_order_id.picking_ids:
                    if picking.state == 'done':
                        order.validated_order = True
                        break
    
    @api.depends('sale_order_id')
    def _compute_picking_done(self):
        records = self
        for order in records:
            order.picking_done = False
            if order.sale_order_id and order.sale_order_id.picking_ids:
                # Filtra solo entregas originales (no devoluciones)
                deliveries = order.sale_order_id.picking_ids.filtered(
                    lambda p: p.picking_type_id.code == 'outgoing' and not p.origin.startswith('Return')
                )
                order.picking_done = True
                for picking in deliveries:
                    if picking.state == 'done':
                        order.picking_done = False
                        break
    
    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        # limiar lineas antes
        self.product_line_ids = [(5, 0, 0)]
        if self.sale_order_id and self.sale_order_id.order_line:
            self.product_line_ids = self.sale_order_id.order_line.mapped(lambda line: (
                (0, 0, {
                    'product_id': line.product_id.id,
                    'quantity': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'tax_ids': [(6, 0, line.tax_id.ids)],
                    'discount': line.discount,
                })
            ))
        else:
            self.product_line_ids = False
            
    def _update_sale_order_lines_from_wizard(self):
        self.ensure_one()
        order = self.sale_order_id
        # Mapear productos en la orden de venta
        sale_lines_by_product = {
            line.product_id.id: line
            for line in order.order_line
        }
        # Productos que ya están en la orden y deben actualizarse
        processed_product_ids = set()
        for wiz_line in self.product_line_ids:
            product_id = wiz_line.product_id.id
            quantity = wiz_line.quantity
            price_unit = wiz_line.price_unit
            tax_ids = wiz_line.tax_ids.ids
            sale_line = sale_lines_by_product.get(product_id)
            if sale_line:
                processed_product_ids.add(product_id)
                # Verificar si hay cambios en cantidad o precio
                if (
                    float_compare(sale_line.product_uom_qty, quantity, precision_rounding=0.00001) != 0 or
                    float_compare(sale_line.price_unit, price_unit, precision_rounding=0.00001) != 0 or
                    set(sale_line.tax_id.ids) != set(tax_ids)
                ):
                    sale_line.write({
                        'product_uom_qty': quantity,
                        'price_unit': price_unit,
                        'tax_id': [(6, 0, tax_ids)],
                    })
            else:
                # Producto no estaba en la orden, agregar
                order.write({
                    'order_line': [(0, 0, {
                        'product_id': product_id,
                        'product_uom_qty': quantity,
                        'price_unit': price_unit,
                        'tax_id': [(6, 0, tax_ids)],
                        'name': wiz_line.product_id.name,
                    })]
                })
                processed_product_ids.add(product_id)
        # Para productos que estaban en la orden pero no están en el wizard
        for line in order.order_line:
            if line.product_id.id not in processed_product_ids:
                if float_compare(line.product_uom_qty, 0.0, precision_rounding=0.00001) != 0:
                    line.write({'product_uom_qty': 0.0})

    def action_confirm(self):
        if not self.sale_order_id:
            raise UserError(_("You must select at least one sales order."))
        if self.more_order:
            raise UserError(_("Review and validate the quote from the quotes menu."))
        if not self.product_line_ids:
            raise UserError(_("You must add at least one product to the sale."))
        if not self.payment_method_ids:
            raise UserError(_("You must add at least one payment method."))
        # validamos los montos de los pagos
        self._validate_amounts()
        # sincronizamos las lineas de la orden de venta con las del asistente
        self._update_sale_order_lines_from_wizard()
        # creamos la orden de venta
        order = self.sale_order_id
        self._valit_sale_order(order)
        # creamos la factura de la orden de venta
        invoice = self._create_invoice(order)
        # creamos los pagos asociados a la factura
        self._create_payments(invoice)
        # creamos el movimiento de sesion
        self._create_movement(
            partner_id = self.sale_order_id.partner_id.id,
            amount = sum(pl.price_total for pl in self.product_line_ids),
            type_op = 'quote',
            order = order,
            obj_related = invoice
        )
        
class CashBoxQuotationLineWizard(models.TransientModel):
    _name = 'cash.box.quotation.line.wizard'
    _description = 'Cash Box Quotation Line Wizard'

    cash_quotation_id = fields.Many2one('cash.box.quotation.wizard', string='Cash Quotation Wizard', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='cash_quotation_id.currency_id', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    qty_available = fields.Float('Quantity On Hand', compute='_compute_quantities', readonly=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    price_unit = fields.Float(string='Unit Price', required=True, default=0.0)
    tax_ids = fields.Many2many('account.tax', string='Taxes', domain=[('type_tax_use', '=', 'sale')])
    discount = fields.Float(string='Discount (%)', digits=0, default=0.0)
    price_tax = fields.Monetary(string='Tax', compute='_compute_prices', store=True)
    price_total = fields.Monetary(string='Total', compute='_compute_prices', store=True)
    
    @api.depends('product_id')
    def _compute_quantities(self):
        ctx = self._context.copy()
        records = self
        for line in records:
            line.qty_available = 0
            if line.product_id:
                # obtenemos el almacen configurado en la caja
                location_id =  line.cash_quotation_id.cash_id.warehouse_id.lot_stock_id.id
                ctx['location'] = location_id
                qty_values = line.product_id.with_context(ctx)._compute_quantities_dict(self._context.get('lot_id'),
                                                                                        self._context.get('owner_id'),
                                                                                        self._context.get('package_id'),
                                                                                        self._context.get('from_date'),
                                                                                        self._context.get('to_date'))[line.product_id.id]
                line.qty_available = qty_values['qty_available']
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.quantity = 1.0
            self.price_unit = self.product_id.list_price
            self.tax_ids = [(6, 0, self.product_id.taxes_id.filtered(lambda t: t.type_tax_use == 'sale').ids)]
        else:
            self.quantity = 0.0
            self.price_unit = 0.0
            self.tax_ids = False
    
    @api.depends('tax_ids', 'quantity', 'price_unit', 'discount')
    def _compute_prices(self):
        for line in self:
            base = line.price_unit * (1 - (line.discount or 0.0) / 100.0) * line.quantity
            total_tax = 0.0
            for tax in line.tax_ids:
                if tax.amount_type == 'percent':
                    total_tax += (tax.amount / 100) * base
                elif tax.amount_type == 'fixed':
                    total_tax += tax.amount
            line.price_tax = total_tax
            line.price_total = base + total_tax
