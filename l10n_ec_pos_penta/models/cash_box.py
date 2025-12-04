# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CashBox(models.Model):
    _name = 'cash.box'
    _description = 'Cash box'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    _sql_constraints = [
        ('unique_cash_box_name', 'unique(name)', _('The box name already exists.')),
        ('unique_session_seq_id', 'unique(session_seq_id)', _('The session sequence must be unique per cash box.')),
        ('unique_movement_seq_id', 'unique(movement_seq_id)', _('The movement sequence must be unique per cash box.')),
    ]

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(string="Code", required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse", check_company=True, tracking=True)
    journal_ids = fields.Many2many('account.journal', string="Journals")
    session_ids = fields.One2many('cash.box.session', 'cash_id', string="Sessions", readonly=True)
    current_session_id = fields.Many2one('cash.box.session', string="Current Session", readonly=True)
    state = fields.Selection([('open', 'Open'), ('closed', 'Closed')], default='closed', string="State", readonly=True)
    is_cash_box_admin = fields.Boolean(compute='_compute_is_cash_box_admin', store=False)
    is_administrator = fields.Boolean(compute='_compute_is_administrator', store=False)
    is_cash_box_responsible = fields.Boolean(compute='_compute_is_cash_box_responsible', store=False)
    # Campos de configuracion
    responsible_ids = fields.Many2many('res.users', 'cash_user_rel', 'cash_id', 'user_id', domain=[('share', '=', False)], default=lambda self: [self.env.uid], string="Responsibles", tracking=True)
    cashier_ids = fields.Many2many('res.users', 'cash_aditional_user_rel', 'cash_id', 'user_id', domain=[('share', '=', False)], string="Cashiers")
    session_seq_id = fields.Many2one('ir.sequence', string="Session Sequence", domain="[('code', '=', 'cash.session')]", required=True)
    movement_seq_id = fields.Many2one('ir.sequence', string="Movement Sequence", domain="[('code', '=', 'cash.session.movement')]")
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
    
    @api.constrains('journal_ids')
    def _check_unique_journal(self):
        for rec in self:
            # Mismo diario de apertura
            if rec.journal_ids:
                other = self.env['cash.box'].search([
                    ('id', '!=', rec.id),
                    ('journal_ids', '=', rec.journal_ids.ids),
                    ('company_id', '=', rec.company_id.id)
                ], limit=1)
                if other:
                    raise UserError(_("The journal '%s' is already assigned to the cash box '%s'. Please choose another journal.") % (", ".join(rec.journal_ids.mapped('name')), other.name))
    
    @api.depends('name')
    def _compute_is_cash_box_admin(self):
        for rec in self:
            rec.is_cash_box_admin = self.env.user.has_group('l10n_ec_pos_penta.group_cash_box_admin')
            
    @api.depends_context('uid')
    def _compute_is_administrator(self):
        for rec in self:
            if self.env.user.has_group('l10n_ec_pos_penta.group_cash_box_admin'):
                rec.is_administrator = True
            else:
                rec.is_administrator = self.env.user in rec.responsible_ids
    
    @api.depends('name')
    def _compute_is_cash_box_responsible(self):
        for rec in self:
            rec.is_cash_box_responsible = self.env.user in rec.responsible_ids
                
    def asign_cash_user_group(self, user):
        user_group = self.env.ref('l10n_ec_pos_penta.group_cash_box_user')
        if not user.has_group('l10n_ec_pos_penta.group_cash_box_user'):
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
