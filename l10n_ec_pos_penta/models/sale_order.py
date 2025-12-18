# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    cash_session_id = fields.Many2one('cash.box.session', string='Cash Session', readonly=True)
    code_movement = fields.Char(string='Code Movement', readonly=True)
    
    @api.model
    def default_get(self, fields_list):
        if 'cash_session_id' not in fields_list:
            fields_list.append('cash_session_id')
        if 'warehouse_id' not in fields_list:
            fields_list.append('warehouse_id')
        res = super().default_get(fields_list)
        if self.env.user.has_group('l10n_ec_pos_penta.group_cash_box_user'):
            cash_box = self.env['cash.box'].search(['|',('cashier_ids', 'in', self.env.user.id),('responsible_ids', 'in', self.env.user.id)], limit=1)
            if not cash_box:
                raise UserError(_("The user is not assigned to any register. Assign a register before creating an order."))
            session = cash_box.current_session_id
            if not session:
                raise UserError(_("You don't have any open cashier sessions. Please open one before creating an order."))
            res['cash_session_id'] = session.id
            res['warehouse_id'] = cash_box.warehouse_id.id
        return res
    
    def action_confirm(self):
        if self.cash_session_id.state == 'closed':
            raise UserError(_("This sales order is related to an already closed cashier session."))
        return super().action_confirm()
    
    def _prepare_invoice(self):
        """ Prepara los valores para crear la factura a partir de la orden de venta.
        :return: dict, values para crear la factura
        """
        res = super()._prepare_invoice()
        # Si hay un cash_session_id o payment_method_id en el wizard, pasalo a la factura
        if self.env.context.get('default_cash_session_id'):
            res['cash_session_id'] = self.env.context.get('default_cash_session_id')
        if self.env.context.get('default_payment_method_id'):
            res['pos_payment_method_id'] = self.env.context.get('default_payment_method_id')
        if self.env.context.get('default_l10n_ec_sri_payment_id'):
            res['l10n_ec_sri_payment_id'] = self.env.context.get('default_l10n_ec_sri_payment_id')
        return res
    
    