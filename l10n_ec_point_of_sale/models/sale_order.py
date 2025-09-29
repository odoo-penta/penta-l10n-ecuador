# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    cash_session_id = fields.Many2one('cash.box.session', string='Cash Session', readonly=True)
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.user.has_group('l10n_ec_point_of_sale.group_cash_box_user'):
            cash_box = self.env['cash.box'].search(['|',('cashier_ids', 'in', self.env.user.id),('responsible_ids', 'in', self.env.user.id)], limit=1)
            if not cash_box:
                raise UserError(_("The user is not assigned to any register. Assign a register before creating an order."))
            session = cash_box.current_session_id
            if not session:
                raise UserError(_("You don't have any open cashier sessions. Please open one before creating an order."))
            # Sólo asigna si los campos están en fields_list
            if 'cash_session_id' in fields_list:
                res['cash_session_id'] = session.id
            if 'warehouse_id' in fields_list:
                res['warehouse_id'] = cash_box.warehouse_id.id
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        orders  = super().create(vals_list)
        for order in orders:
            if order.cash_session_id:
                self.env['cash.box.session']._create_movement(order.cash_session_id.id, order.partner_id.id, 'order', order.id)
        return orders
    
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
    
    