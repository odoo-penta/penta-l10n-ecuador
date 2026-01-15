# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    cash_session_id = fields.Many2one('cash.box.session', string="Cash Session", copy=False)
    code_movement = fields.Char(string='Code Movement', readonly=True)
    show_cash_session = fields.Boolean()
    allowed_cash_boxes = fields.Many2many('cash.box')
    is_cashbox_deposit = fields.Boolean()
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Buscar sesiones abiertas del usuario
        cash_boxs = self.env['cash.box'].search([('state', '=', 'open'),'|',('cashier_ids', 'in', self.env.user.id),('responsible_ids', 'in', self.env.user.id)])
        # Mostrar campo solo si tiene más de una sesión
        res['show_cash_session'] = len(cash_boxs) > 1
        res['allowed_cash_boxes'] = [(6, 0, cash_boxs.ids)]
        # Si solo hay una sesión, asignarla automáticamente
        if len(cash_boxs) == 1:
            res['cash_session_id'] = cash_boxs.current_session_id.id
        
        if res.get('is_cashbox_deposit') and res.get('cash_session_id'):
            company = self.env.company
            res['partner_id'] = company.partner_id.id
            session = self.env['cash.box.session'].browse(res['cash_session_id'])
            close_account = session.cash_id.close_account_id

            if close_account:
                res['destination_account_id'] = close_account.id
            #     res['payment_mode'] = 'expense'
            #     res['expense_line_ids'] = [(0, 0, {
            #         'account_id': close_account.id,
            #         'amount_cash': res.get('amount', 0.0),
            #     })]
        return res
        
    def action_post(self):
        for payment in self:
            session = payment.cash_session_id
            movement = False
            is_deposit = payment.is_cashbox_deposit
            if session and not is_deposit:
                if session.state == 'closed':
                    raise UserError(_("This sales order is related to an already closed cashier session."))
                if payment.env['cash.box.session.movement'].get_sequence(session.id):
                    movement = payment.env['cash.box.session']._create_movement(session.id, payment.partner_id.id, 'payment', payment.id)
                    payment.code_movement = movement.name
            approval_deposit = self.search([
                ('cash_session_id', '=', session.id),
                ('is_cashbox_deposit', '=', True),
                ('state', 'not in', ('draft', 'canceled', 'rejected'))])
            if approval_deposit:
                raise UserError(_("You cannot confirm the deposit because we already have a confirmed deposit for the session: %s" % session.name))
        res = super().action_post()
        for payment in self:
            if payment.move_id and session and not is_deposit:
                ref = session.name
                if movement:
                    ref = session.name + ' - ' + movement.name
                if payment.move_id.ref:
                    payment.move_id.ref += ' - ' + ref
                else:
                    payment.move_id.ref = ref
                for move_line in payment.move_id.line_ids:
                    move_line.name += ' - ' + ref
            if is_deposit:
                session.deposit_id = payment.id
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        # for vals in vals_list:
        #     if vals.get('is_cashbox_deposit') and vals.get('cash_session_id'):
        #         session = self.env['cash.box.session'].browse(vals['cash_session_id'])
        #         close_account = session.cash_id.close_account_id

        #         if close_account:
        #             vals['payment_mode'] = 'expense'

        #             vals['expense_line_ids'] = [(0, 0, {
        #                 'account_id': close_account.id,
        #                 'amount_cash': vals.get('amount', 0.0),
        #             })]
        payments  = super().create(vals_list)
        for payment in payments:
            if not payment.cash_session_id and self.env.user.has_group('l10n_ec_pos_penta.group_cash_box_user') and payment.payment_type == 'inbound':
                show_error = False
                cash_box = self.env['cash.box'].search(['|',('cashier_ids', 'in', self.env.user.id),('responsible_ids', 'in', self.env.user.id)], limit=1)
                if not cash_box:
                    show_error = True
                else:
                    session = cash_box.current_session_id
                    if not session:
                        show_error = True
                if show_error and payment.is_cashbox_deposit:
                    # Allow deposits without an open session
                    continue 
                if show_error:
                    raise UserError(_("The checkout session enabled for this user to record customer payments is closed. Please open the checkout session to enable customer payment recording."))
                payment.cash_session_id = session.id
        return payments

    def write(self, vals):
        res = super().write(vals)

        for payment in self:
            if payment.is_cashbox_deposit and payment.cash_session_id:
                close_account = payment.cash_session_id.cash_id.close_account_id
                if close_account and not payment.expense_line_ids:
                    payment.expense_line_ids = [(0, 0, {
                        'account_id': close_account.id,
                        'amount_cash': payment.amount,
                    })]
        return res
    
    def _prepare_move_line_default_vals(self, **kwargs):
        # Detectar si penta_anticipos está instalado
        module_installed = self.env['ir.module.module'].sudo().search([
            ('name', '=', 'penta_anticipos'),
            ('state', '=', 'installed')
        ], limit=1)

        if module_installed and self.is_cashbox_deposit:
            return super(
                AccountPayment,
                self.with_context(force_is_invoice_payment=True)
            )._prepare_move_line_default_vals(**kwargs)

        return super()._prepare_move_line_default_vals(**kwargs)
