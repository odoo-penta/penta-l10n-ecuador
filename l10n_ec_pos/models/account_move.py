# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    cash_session_id = fields.Many2one('cash.box.session', string="Cash Session", copy=False)
    code_movement = fields.Char(string='Code Movement', readonly=True)
    show_cash_session = fields.Boolean()
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Buscar sesiones abiertas del usuario
        cash_boxs = self.env['cash.box'].search([('state', '=', 'open'),'|',('cashier_ids', 'in', self.env.user.id),('responsible_ids', 'in', self.env.user.id)])
        # Mostrar campo solo si tiene más de una sesión
        res['show_cash_session'] = len(cash_boxs) > 1
        # Si solo hay una sesión, asignarla automáticamente
        if len(cash_boxs) == 1:
            res['cash_session_id'] = cash_boxs.current_session_id.id
        return res
    
    def action_post(self):
        if self.cash_session_id:
            if self.cash_session_id.state == 'closed':
                raise UserError(_("This invoice is related to an already closed cashier session."))
            movement = self.env['cash.box.session']._create_movement(self.cash_session_id.id, self.partner_id.id, 'invoice', self.id)
            for line in self.line_ids:
                if not line.name:
                    line.name = movement.name
                else:
                    line.name += ' - ' + movement.name
        return super().action_post()
    
    @api.model_create_multi
    def create(self, vals_list):
        moves  = super().create(vals_list)
        for move in moves:
            if not move.cash_session_id and self.env.user.has_group('l10n_ec_pos.group_cash_box_user') and move.move_type == 'out_invoice':
                cash_box = self.env['cash.box'].search(['|',('cashier_ids', 'in', self.env.user.id),('responsible_ids', 'in', self.env.user.id)], limit=1)
                if not cash_box:
                    raise UserError(_("The user is not assigned to any register. Assign a register before creating an payment."))
                session = cash_box.current_session_id
                if not session:
                    raise UserError(_("You don't have any open cashier sessions. Please open one before creating an payment."))
                move.cash_session_id = session.id
        return moves
