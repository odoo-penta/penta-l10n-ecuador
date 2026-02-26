# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    type_account=fields.Selection([
        ('savings', 'Cuenta de ahorros'),
        ('checking', 'Cuenta Corriente')]
        ,default='savings',required=True)
