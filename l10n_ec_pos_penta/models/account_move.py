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
    
    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        super()._onchange_journal_id()
        self.cash_session_id = False
        if self.journal_id:
            # Buscar caja abierta asociada al diario y usuario
            cash_boxs = self.env['cash.box'].search([
                ('state', '=', 'open'),
                ('journal_id', '=', self.journal_id.id),
                '|',
                ('cashier_ids', 'in', self.env.user.id),
                ('responsible_ids', 'in', self.env.user.id)
            ])
            self.show_cash_session = len(cash_boxs) > 1
            if len(cash_boxs) == 1:
                self.cash_session_id = cash_boxs.current_session_id.id
    
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
