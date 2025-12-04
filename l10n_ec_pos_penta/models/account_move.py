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
    
    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        super()._onchange_journal_id()
        self.cash_session_id = False
        if self.journal_id:
            # Buscar caja abierta asociada al diario y usuario
            cash_boxs = self.env['cash.box'].search([
                ('state', '=', 'open'),
                ('journal_ids', 'in', self.journal_id.id),
                '|',
                ('cashier_ids', 'in', self.env.user.id),
                ('responsible_ids', 'in', self.env.user.id)
            ])
            self.show_cash_session = len(cash_boxs) > 1
            if len(cash_boxs) == 1:
                self.cash_session_id = cash_boxs.current_session_id.id
    
    def action_post(self):
        cash_boxs = self.env['cash.box'].search([
            ('state', '=', 'open'),
            ('journal_ids', 'in', self.journal_id.id),
            '|',
            ('cashier_ids', 'in', self.env.user.id),
            ('responsible_ids', 'in', self.env.user.id)
        ])
        if not self.cash_session_id and len(cash_boxs) == 1:
            self.cash_session_id = cash_boxs.current_session_id.id
        if self.cash_session_id:
            if self.cash_session_id.state == 'closed':
                raise UserError(_("This invoice is related to an already closed cashier session."))
        return super().action_post()
