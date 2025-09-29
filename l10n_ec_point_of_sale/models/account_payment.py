# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    cash_session_id = fields.Many2one('cash.box.session', string="Cash Session", copy=False)

    @api.model
    def default_get(self, fields_list):
        #import pdb;pdb.set_trace()
        res = super().default_get(fields_list)
        if self.env.user.has_group('l10n_ec_point_of_sale.group_cash_box_user') and fields_list.get('payment_type') == 'inbound':
            cash_box = self.env['cash.box'].search(['|',('cashier_ids', 'in', self.env.user.id),('responsible_ids', 'in', self.env.user.id)], limit=1)
            if not cash_box:
                raise UserError(_("The user is not assigned to any register. Assign a register before creating an order."))
            session = cash_box.current_session_id
            if not session:
                raise UserError(_("You don't have any open cashier sessions. Please open one before creating an order."))
            # Sólo asigna si los campos están en fields_list
            if 'cash_session_id' in fields_list:
                res['cash_session_id'] = session.id
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        #import pdb;pdb.set_trace()
        payments  = super().create(vals_list)
        for payment in payments:
            if payment.cash_session_id:
                self.env['cash.box.session']._create_movement(payment.cash_session_id.id, payment.partner_id.id, 'payment', payment.id)
        return payments
