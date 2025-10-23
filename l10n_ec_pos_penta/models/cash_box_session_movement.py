# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CashBoxSessionMovement(models.Model):
    _name = 'cash.box.session.movement'
    _description = 'Cash Box Session Movement'
    _order = 'name desc'

    name = fields.Char(required=True, copy=False, readonly=True, default=_('New'))
    session_id = fields.Many2one('cash.box.session', string="Cash Box Session", readonly=True)
    currency_id = fields.Many2one(related='session_id.currency_id', depends=['session_id'])
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    operation_type = fields.Selection([
        ('order', 'Order'),
        ('invoice', 'Invoice'),
        ('payment', 'Payment'),
    ], string="Operation Type", required=True)
    amount = fields.Monetary(string='Amount', compute='_compute_amount', currency_field='currency_id')
    cashier_id = fields.Many2one('res.users', 'Cashier', default=lambda self: self.env.user)
    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True)
    credit_note_id = fields.Many2one("account.move", string="Credit Note", readonly=True)
    payment_id = fields.Many2one("account.payment", string="Payment", readonly=True)
    order_id = fields.Many2one("sale.order", string="Sale Order", readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('done', 'Done'),
    ], string='Financial statement', compute='_compute_state', store=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # asignamos un nombre unico al movimiento en base a la secuencia
            if vals.get('name', 'New') == 'New':
                seq = self.get_sequence(vals.get('session_id', None))
                if seq:
                    vals['name'] = seq.next_by_id() or '00000'
                else:
                    raise UserError(_("Please configure the sequence for cash session movements."))
        return super().create(vals_list)
    

    @api.depends('order_id', 'payment_id', 'invoice_id')
    def _compute_amount(self):
        self.amount = 0.00
        for record in self:
            if record.order_id:
                record.amount = record.order_id.amount_total
            elif record.payment_id:
                record.amount = record.payment_id.amount
            elif record.invoice_id:
                record.amount = record.invoice_id.amount_total

    
    @api.model
    def get_sequence(self, session_id=None):
        # obtenemos la secuencia para el movimiento
        if session_id:
            session = self.env['cash.box.session'].browse(session_id)
            return session.cash_id.movement_seq_id or False
        elif self.session_id:
            return self.session_id.cash_id.session_seq_id or False
        else:
            session_id = self.env.context.get('default_session_id', False)
            if session_id:
                return self.env['cash.box.session'].browse(session_id).cash_id.movement_seq_id or False
            return False
        
    @api.depends('invoice_id.state', 'credit_note_id.state', 'payment_id.state', 'order_id.state', 'operation_type')
    def _compute_state(self):
        for rec in self:
            state = 'draft'  # valor por defecto
            if rec.operation_type == 'order' and rec.order_id:
                state = rec.order_id.state
            elif rec.operation_type == 'invoice' and rec.invoice_id:
                state = rec.invoice_id.state
            elif rec.operation_type == 'payment' and rec.payment_id:
                state = rec.payment_id.state
            # Mapeamos algunos states si se requiere simplificar
            if state in ['not_paid', 'draft']:
                rec.state = 'draft'
            elif state in ['posted', 'open', 'sent']:
                rec.state = 'posted'
            elif state in ['paid']:
                rec.state = 'paid'
            elif state in ['cancel', 'canceled']:
                rec.state = 'cancelled'
            elif state in ['sale', 'done']:
                rec.state = 'done'
            else:
                rec.state = 'draft'