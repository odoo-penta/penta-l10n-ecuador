# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.AbstractModel):
    _inherit = 'sale.order'
    
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
    
    