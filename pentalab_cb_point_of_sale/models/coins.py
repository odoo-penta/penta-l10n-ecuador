# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)

from odoo import models, fields, api, _
from babel.numbers import format_currency


class CashBoxCoin(models.Model):
    _name = 'cash.box.coin'
    _description = 'Cash box Coin'
    _order = 'name desc'
    
    _sql_constraints = [
        ('unique_cash_box_coin', 'unique(name)', _('The coin name already exists.')),
    ]
    
    name = fields.Char(string="Name", readonly=True)
    value = fields.Float(required=True)
    currency_id = fields.Many2one('res.currency', string="Currency", required=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'value' in vals:
                currency = self.env.user.company_id.currency_id
                lang = self.env.user.lang or 'en_US'
                vals['name'] = format_currency(vals['value'], currency.name, locale=lang)
                vals['currency_id'] = currency.id
        return super().create(vals)

    def write(self, vals):
        if 'value' in vals:
            for rec in self:
                currency = rec.currency_id or self.env.user.company_id.currency_id
                lang = self.env.user.lang or 'en_US'
                rec.name = format_currency(rec.value, currency.name, locale=lang)
        return super().write(vals)
