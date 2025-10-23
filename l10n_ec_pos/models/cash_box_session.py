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
                    vals['name'] = seq.next_by_id() or '00000'
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
        payments = self._get_payments().filtered(lambda p: p.journal_id.type == 'cash')
        if not payments:
            return {}
        # Agrupar movimientos por cuenta de los pagos relacionados (efectivo)
        payment_datas = {}
        for payment in payments:
            if payment_datas.get(payment.journal_id.default_account_id.id):
                payment_datas[payment.journal_id.default_account_id.id] += payment.amount
            else:
                payment_datas[payment.journal_id.default_account_id.id] = payment.amount
        return payment_datas
        
    def create_closing_journal_entries(self):
        payment_datas = self._get_payment_datas()
        if payment_datas:
            # Creamos el asiento de cierre
            reference = _('Cash closing %s') % (self.name)
            move = self.env['account.move'].create({
                'ref': reference,
                'journal_id': self.cash_id.close_journal_id.id,
                'date': fields.Date.context_today(self),
                'move_type': 'entry',
            })
            line_vals = []
            for account_id, amount in payment_datas.items():
                # Agg la linea al credito por cuenta de pago
                line_vals.append((0, 0, {
                    'move_id': move.id,
                    'account_id': account_id,
                    'debit': 0.00,
                    'credit': amount,
                    'name': self.name,
                }))
            # Agg la linea al debito por cuenta de cierre
            line_vals.append((0, 0, {
                'move_id': move.id,
                'account_id': self.cash_id.close_account_id.id,
                'debit': sum(payment_datas.values()),
                'credit': 0.00,
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
        
    def _get_payments(self):
        """ Obtiene los pagos realizados con la sesion"""
        return self.env['account.payment'].search([('cash_session_id', '=', self.id),('state', 'in', ['in_process', 'paid'])])
    
    def _get_invoices(self):
        """ Obtiene los pagos realizados con la sesion"""
        return self.env['account.move'].search([('move_type' ,'in', ['out_invoice', 'in_invoice']),('cash_session_id', '=', self.id),('state', '=', 'posted')])
          
    def open_invoices_view(self):
        self.ensure_one()
        # Obtener pagos de los movimientos
        invoices = self._get_invoices()
        list_view_id = self.env.ref('account.view_out_invoice_tree').id
        form_view_id = self.env.ref('account.view_move_form').id
        return {
            'name': 'Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'views': [(list_view_id, 'list'), (form_view_id, 'form')],
            'domain': [('id', 'in', invoices.ids)],
            'target': 'current',
            'context': {'create': False},
        }
    
    def open_payments_view(self):
        self.ensure_one()
        # Obtener pagos de los movimientos
        payments = self._get_payments()
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
        invoice_moves = self._get_invoices().mapped('move_id') if self._get_invoices() else self.env['account.move']
        payment_moves = self._get_payments().mapped('move_id') if self._get_payments() else self.env['account.payment']
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
    
    def _get_payment_summary(self):
        """ Obtiene un resumen de los pagos realizados por movimiento """
        def categorize_payment(payment):
            """ Categoriza el pago según su tipo """
            if payment.journal_id.type == 'bank':
                if payment.card_id:
                    return 'card'
                else:
                    return 'transfer'
            else:
                return 'cash'

        payment_summary = {}
        payments = self._get_payments()
        for payment in payments:
            key = categorize_payment(payment)
            if payment_summary.get(payment.id):
                payment_summary[payment.id][key] += payment.amount
            else:
                payment_summary[payment.id] = {'cash': 0.00, 'transfer': 0.00, 'card': 0.00}
                payment_summary[payment.id][key] += payment.amount
        return payment_summary
    
    def get_payment_summary_by_journal(self):
        summary = defaultdict(float)
        for payment in self._get_payments():
            journal_name = payment.journal_id.name
            summary[journal_name] += payment.amount
        return dict(summary)
    
    def print_summary(self):
        self.ensure_one()
        return self.env.ref('l10n_ec_pos.action_cash_closing_report').report_action(self)
