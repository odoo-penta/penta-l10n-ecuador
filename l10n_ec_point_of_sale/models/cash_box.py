# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from collections import defaultdict


class CashBox(models.Model):
    _name = 'cash.box'
    _description = 'Cash box'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    _sql_constraints = [
        ('unique_cash_box_name', 'unique(name)', _('The box name already exists.')),
    ]

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(string="Code", required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse", check_company=True, tracking=True)
    journal_id = fields.Many2one('account.journal', string="Journal", domain=[('type', 'in', ['sale'])], tracking=True)
    session_ids = fields.One2many('cash.box.session', 'cash_id', string="Sessions", readonly=True)
    current_session_id = fields.Many2one('cash.box.session', string="Current Session", readonly=True)
    state = fields.Selection([('open', 'Open'), ('closed', 'Closed')], default='closed', string="State", readonly=True)
    is_cash_box_admin = fields.Boolean(compute='_compute_is_cash_box_admin', store=False)
    is_administrator = fields.Boolean(compute='_compute_is_administrator', store=False)
    is_cash_box_responsible = fields.Boolean(compute='_compute_is_cash_box_responsible', store=False)
    # Campos de configuracion
    responsible_ids = fields.Many2many('res.users', 'cash_user_rel', 'cash_id', 'user_id', default=lambda self: [self.env.uid], string="Responsibles", tracking=True)
    cashier_ids = fields.Many2many('res.users', 'cash_aditional_user_rel', 'cash_id', 'user_id', string="Cashiers")
    session_seq_id = fields.Many2one('ir.sequence', string="Session Sequence", domain="[('code', '=', 'cash.session')]", required=True)
    movement_seq_id = fields.Many2one('ir.sequence', string="Movement Sequence", domain="[('code', '=', 'cash.session.movement')]", required=True)
    close_account_id = fields.Many2one('account.account', required=True, check_company=True, copy=False, ondelete='restrict', tracking=True, string='Close Account', domain=[('deprecated', '=', False),('account_type', '=', 'asset_cash')])
    gain_account_id = fields.Many2one('account.account', required=True, check_company=True, copy=False, ondelete='restrict', tracking=True, string='Gain Account', domain=[('deprecated', '=', False),('account_type', '=', 'income')])
    loss_account_id = fields.Many2one('account.account', required=True, check_company=True, copy=False, ondelete='restrict', tracking=True, string='Loss Account', domain=[('deprecated', '=', False),('account_type', '=', 'expense')])
    close_journal_id = fields.Many2one('account.journal', string="Close Journal", domain=[('type', 'in', ['general'])], tracking=True)
    l10n_ec_sri_payment_id = fields.Many2one('l10n_ec.sri.payment', string="SRI Payment Method", required=True)
    analytic_account_id = fields.Many2one('account.analytic.account', required=True, ondelete='restrict', tracking=True, domain="['|', ('company_id', '=', False), ('company_id', '=?', company_id)]")
    
    @api.model_create_multi
    def create(self, vals_list):
        for record in vals_list:
            if record.get('responsible_ids'):
                for responsible in record['responsible_ids'][0]:
                    self.asign_cash_user_group(self.env['res.users'].browse(responsible))
            if record.get('cashier_ids'):
                for responsible in record['cashier_ids'][0]:
                    self.asign_cash_user_group(self.env['res.users'].browse(responsible))
        return super().create(vals_list)
    
    def write(self, vals):
        if self.current_session_id and not self.env.context.get('closed', False):
            raise UserError(_("You must close the current session before making changes to the box."))
        if vals.get('responsible_ids'):
            for responsible in vals['responsible_ids'][0]:
                self.asign_cash_user_group(self.env['res.users'].browse(responsible))
        if vals.get('cashier_ids'):
            for responsible in vals['cashier_ids'][0]:
                self.asign_cash_user_group(self.env['res.users'].browse(responsible))
        return super().write(vals)
    
    def unlink(self):
        for cash in self:
            # no permite eliminar caja si ya tiene una session relacionada
            if cash.session_ids:
                raise UserError(_("You cannot delete a cash box with active sessions."))
        return super().unlink()
    
    @api.model
    def search(self, args, offset=0, limit=None, order=None):
        args = list(args)  # Copia segura para evitar efectos colaterales
        # si es administrador de sistema permite ver todas las cajas
        if not self._is_admin():
            # filtra que el usuario se encuentre entre los administradores del sistema
            args += ['|',('responsible_ids', 'in', self.env.uid),('cashier_ids', 'in', self.env.uid)]
        return super().search(args, offset=offset, limit=limit, order=order)
    
    @api.constrains('journal_id', 'close_journal_id')
    def _check_unique_journals(self):
        for rec in self:
            # Mismo diario de apertura
            if rec.journal_id:
                other = self.env['cash.box'].search([
                    ('id', '!=', rec.id),
                    ('journal_id', '=', rec.journal_id.id),
                    ('company_id', '=', rec.company_id.id)
                ], limit=1)
                if other:
                    raise UserError(_("The journal '%s' is already assigned to the cash box '%s'. Please choose another journal.") % (rec.journal_id.name, other.name))
            # Mismo diario de cierre
            if rec.close_journal_id:
                other = self.env['cash.box'].search([
                    ('id', '!=', rec.id),
                    ('close_journal_id', '=', rec.close_journal_id.id),
                    ('company_id', '=', rec.company_id.id)
                ], limit=1)
                if other:
                    raise UserError(_("The close journal '%s' is already assigned to the cash box '%s'. Please choose another journal.") % (rec.close_journal_id.name, other.name))

    @api.constrains('cashier_ids')
    def _check_unique_cashier(self):
        for rec in self:
            for user in rec.cashier_ids:
                other = self.env['cash.box'].search([
                    ('id', '!=', rec.id),
                    ('cashier_ids', 'in', user.id),
                    ('company_id', '=', rec.company_id.id)
                ], limit=1)
                if other:
                    raise UserError(_("The cashier '%s' is already assigned to the cash box '%s'. Please choose another cashier.") % (user.name, other.name))
    
    @api.depends('name')
    def _compute_is_cash_box_admin(self):
        for rec in self:
            rec.is_cash_box_admin = self.env.user.has_group('l10n_ec_point_of_sale.group_cash_box_admin')
            
    @api.depends_context('uid')
    def _compute_is_administrator(self):
        for rec in self:
            if self.env.user.has_group('l10n_ec_point_of_sale.group_cash_box_admin'):
                rec.is_administrator = True
            else:
                rec.is_administrator = self.env.user in rec.responsible_ids
    
    @api.depends('name')
    def _compute_is_cash_box_responsible(self):
        for rec in self:
            rec.is_cash_box_responsible = self.env.user in rec.responsible_ids
                
    def asign_cash_user_group(self, user):
        user_group = self.env.ref('l10n_ec_point_of_sale.group_cash_box_user')
        if not user.has_group('l10n_ec_point_of_sale.group_cash_box_user'):
            user.groups_id = [(4, user_group.id, 0)]
        return True
    
    @api.model
    def _is_admin(self):
        return self.env.user.has_group('base.group_system')
    
    def open_cash(self, initial_balance):
        # abrimos la sesion
        session = self.env['cash.box.session'].open_session(self, initial_balance)
        # abrimos caja
        self.state = 'open'
        self.current_session_id = session.id
        # mensaje en bitacora
        message = _("Cash box open successfully with a initial balance of %s.") % (
            initial_balance
        )
        self.message_post(body=message)
        return session
    
    def closed_cash(self, final_balance):
        # establecemos el contexto de cierre
        self = self.with_context(closed=True)
        # cerramos la sesion
        self.current_session_id.closed_session(final_balance)
        # cerramos caja
        self.state = 'closed'
        self.current_session_id = False
        # mensaje en bitacora
        message = _("Cash box closed successfully with a final balance of %s.") % (
            final_balance
        )
        self.message_post(body=message)

    def action_open(self):
        self.ensure_one()
        # invocamos el wizard de apertura
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cash.box.open.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_cash_id': self.id},
        }

    def action_close(self):
        self.ensure_one()
        # invocamos el wizard de cierre
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cash.box.closed.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_cash_id': self.id},
        }
            
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
        return {
            'name': 'Payments',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', payments.ids)],
            'target': 'current',
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
    
    def get_payment_summary_by_journal(self):
        summary = defaultdict(float)
        for move in self.movement_ids:
            if move.payment_id:  # Solo movimientos con payment
                journal_name = move.payment_id.journal_id.name
                summary[journal_name] += move.amount  # Sumamos el total del movimiento
        return dict(summary)
        
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
                    session_name = self.env['cash.box.session'].browse(vals.get('session_id', False)).name.split("/")[-1] if vals.get('session_id') else 'Session'
                    vals['name'] = session_name + '/' + seq.next_by_id() or '00000'
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
