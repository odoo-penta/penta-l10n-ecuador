from odoo import models, fields
import io
import base64
import xlsxwriter


class AccountAccount(models.Model):
    _inherit = 'account.account'

    type_production_cost = fields.Selection([
        ('standar', 'Costo Estándar Aplicado'),
        ('actual', 'Costo Real'),
        ], string='Tipo costo producción')
