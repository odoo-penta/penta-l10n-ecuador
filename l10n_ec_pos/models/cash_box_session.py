# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from collections import defaultdict


class CashBoxSession(models.Model):
    _name = 'cash.box.session'
    _description = 'Cash Box Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(required=True, copy=False, readonly=True, default=_('New'))
    cash_id = fields.Many2one('cash.box', string="Cash Box", readonly=True)
    responsible_open = fields.Many2one('res.users', string="Responsible (Open)", readonly=True)
    responsible_close = fields.Many2one('res.users', string="Responsible (Close)", readonly=True)
    cashier_ids = fields.Many2many(related='cash_id.cashier_ids', depends=['cash_id'], readonly=True)
    currency_id = fields.Many2one(related='cash_id.currency_id', depends=['cash_id'])
    opening_date = fields.Datetime(string="Opening Date", readonly=True)
    closing_date = fields.Datetime(string="Closing Date", readonly=True)
    initial_balance = fields.Monetary(currency_field='currency_id', string="Initial balance", readonly=True)
    final_balance = fields.Monetary(currency_field='currency_id', string="Final balance", readonly=True)
    closing_balance = fields.Monetary(currency_field='currency_id', string="Closing balance", readonly=True)
    suggested_balance = fields.Monetary(currency_field='currency_id', readonly=True)
    diff_balance = fields.Monetary(currency_field='currency_id', readonly=True)
    state = fields.Selection([('in_progress', 'In progress'), ('closed', 'Closed')], default='closed', string="State")
    movement_ids = fields.One2many('cash.box.session.movement', 'session_id', string="Movements", readonly=True)
    close_move_id = fields.Many2one('account.move', readonly=True)
    diff_move_id = fields.Many2one('account.move', readonly=True)
    opening_note = fields.Text(readonly=True)
    closing_note = fields.Text(readonly=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # asignamos un nombre unico a la sesion en base a la secuencia
            if vals.get('name', 'New') == 'New':
                seq = self.get_sequence(vals.get('cash_id', None))
                if seq:
                    cash_name = self.env['cash.box'].browse(vals.get('cash_id', False)).code if vals.get('cash_id') else 'Cash Box'
                    vals['name'] = cash_name + '/' + seq.next_by_id() or '00000'
                else:
                    raise UserError(_("Please configure the sequence for cash box sessions."))
        return super().create(vals_list)
    
    @api.model 
    def open_session(self, cash, initial_balance):
        # creamos la nueva session
        session = self.create({
            'cash_id': cash.id,
            'responsible_open': self.env.user.id,
            'currency_id': cash.currency_id.id,
            'opening_date': fields.Datetime.now(),
            'initial_balance': initial_balance,
            'state': 'in_progress',
        })
        # mensaje en bitacora
        message = _("Cash box '%s' opend successfully with a initial balance of %s.") % (
            cash.name, initial_balance
        )
        session.message_post(body=message)
        return session
    
    @api.model
    def closed_session(self, final_balance):
        self.responsible_close = self.env.user.id
        # creamos el asiento de cierre
        self.create_closing_journal_entries()
        # cerramos la sesion
        self.state = 'closed'
        self.closing_balance = final_balance
        self.final_balance = final_balance - self.initial_balance
        self.closing_date = fields.Datetime.now()
        # mensaje en bitacora
        message = _("Cash box '%s' closed successfully with a final balance of %s.") % (
            self.cash_id.name, final_balance
        )
        self.message_post(body=message)
        
    def _get_payment_datas(self):
        if not self.movement_ids:
            return {}
        # Agrupar movimientos por diario de los pagos relacionados (efectivo)
        payment_datas = {}
        for movement in self.movement_ids:
            payment_data = {}
            # Si el movimiento tiene pago directo, usar su diario
            if movement.payment_id:
                journal = movement.payment_id.journal_id
                payment_data[movement.payment_id.id] = {'journal': journal, 'customer': movement.partner_id, 'amount': movement.amount}
            # si es nota de credito, usar el diario de la nota
            elif movement.credit_note_id:
                journal = movement.credit_note_id.journal_id
                payment_data[movement.credit_note_id.id] = {'journal': journal, 'customer': movement.partner_id, 'amount': movement.amount}
            # Si es factura, buscar los pagos relacionados y agrupar por diario
            elif movement.invoice_id:
                for payment in movement.invoice_id.matched_payment_ids:
                    payment_data[payment.id] = {'journal': payment.journal_id, 'customer': payment.partner_id, 'amount': payment.amount}
            payment_datas[movement.id] = payment_data
        return payment_datas
        
    def create_closing_journal_entries(self):
        payment_datas = self._get_payment_datas()
        if payment_datas:
            # Filtramos pagos de tipo efectivo con monto mayor a 0
            cash_lines_exist = any(
                pp_values_v['amount'] and pp_values_v['journal'].type == 'cash'
                for p_values in payment_datas.values()
                for pp_values_v in p_values.values()
            )
            if cash_lines_exist:
                # Creamos el asiento de cierre
                reference = _('Cash closing %s') % (self.name)
                move = self.env['account.move'].create({
                    'ref': reference,
                    'journal_id': self.cash_id.close_journal_id.id,
                    'date': fields.Date.context_today(self),
                    'move_type': 'entry',
                })
                line_vals = []
                for p_values in payment_datas.values():
                    for pp_values_k, pp_values_v in p_values.items():
                        if not pp_values_v['amount'] or pp_values_v['journal'].type != 'cash':
                            continue
                        # agg la linea al debito
                        line_vals.append((0, 0, {
                            'move_id': move.id,
                            'partner_id': pp_values_v['customer'].id,
                            'account_id': self.cash_id.close_account_id.id,
                            'debit': pp_values_v['amount'],
                            'credit': 0.00,
                            'name': self.name,
                        }))
                        # agg la linea al credito
                        line_vals.append((0, 0, {
                            'move_id': move.id,
                            'partner_id': pp_values_v['customer'].id,
                            'account_id': self.env['account.payment'].browse(pp_values_k).journal_id.default_account_id.id,
                            'debit': 0.00,
                            'credit': pp_values_v['amount'],
                            'name': self.name,
                        }))
                move.write({'line_ids': line_vals})
                move.action_post()
                # Relacionamos el asiento de cierre a la sesion
                self.close_move_id = move.id
     
    @api.model
    def get_sequence(self, cash_id=None):
        # obtenemos la secuencia para la sesion
        if cash_id:
            cash = self.env['cash.box'].browse(cash_id)
            return cash.session_seq_id or False
        elif self.cash_id:
            return self.cash_id.session_seq_id or False
        else:
            cash_id = self.env.context.get('default_cash_id', False)
            if cash_id:
                return self.env['cash.box'].browse(cash_id).session_seq_id or False
            return False
          
    def open_invoices_view(self):
        self.ensure_one()
        # Obtener pagos de los movimientos
        invoice_movements = self.movement_ids.filtered(lambda m: m.invoice_id)
        invoices = invoice_movements.mapped('invoice_id')
        return {
            'name': 'Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoices.ids)],
            'target': 'current',
        }
    
    def open_payments_view(self):
        self.ensure_one()
        # Obtener pagos de los movimientos
        payment_movements = self.movement_ids.filtered(lambda m: m.payment_id)
        payments = payment_movements.mapped('payment_id')
        list_view_id = self.env.ref('account.view_account_payment_tree').id
        form_view_id = self.env.ref('account.view_account_payment_form').id
        return {
            'name': 'Payments',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'views': [(list_view_id, 'list'), (form_view_id, 'form')],
            'domain': [('id', 'in', payments.ids)],
            'target': 'current',
            'context': {'create': False},
        }
        
    def open_journal_items_view(self):
        self.ensure_one()
        # Obtener asientos de facturas y pagos
        invoice_movements = self.movement_ids.filtered(lambda m: m.invoice_id)
        payment_movements = self.movement_ids.filtered(lambda m: m.payment_id)
        invoice_moves = invoice_movements.mapped('invoice_id')
        payment_moves = payment_movements.mapped('payment_id.move_id')
        # Unirlos valores
        move_ids = (invoice_moves + payment_moves)
        # Si tenemos asiento de cierre lo agg
        if self.close_move_id:
            move_ids |= self.close_move_id
        # Buscamos los apuntes contables de los asientos
        move_lines = self.env['account.move.line'].search([
            ('move_id', 'in', move_ids.ids)
        ])
        return {
            'name': 'Journal Items',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [('id', 'in', move_lines.ids)],
            'target': 'current',
            'context': {'create': False},
        }
        
    def _create_movement(self, session_id, partner_id, type_op, obj_related):
        # creamos un movimiento de 
        values = {
            'session_id': session_id,
            'partner_id': partner_id,
            'cashier_id': self.env.user.id,
            'operation_type': type_op,
        }
        if type_op == 'order':
            values['order_id'] = obj_related
        elif type_op == 'payment':
            values['payment_id'] = obj_related
        elif type_op == 'invoice':
            values['invoice_id'] = obj_related
        return self.env['cash.box.session.movement'].create(values)
    
    def print_summary(self):
        self.ensure_one()
        return self.env.ref('l10n_ec_pos.action_cash_closing_report').report_action(self)
    
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
    
    def get_payment_summary_by_journal(self):
        summary = defaultdict(float)
        for move in self.movement_ids:
            if move.payment_id:  # Solo movimientos con payment
                journal_name = move.payment_id.journal_id.name
                summary[journal_name] += move.amount  # Sumamos el total del movimiento
        return dict(summary)