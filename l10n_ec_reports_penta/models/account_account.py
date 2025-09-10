from odoo import models, fields

class AccountAccount(models.Model):
    _inherit = 'account.account'

    hide_in_report = fields.Boolean(string="Ocultar en reporte",default= False)


class AccountGroup(models.Model):
    _inherit = 'account.group'

    account_move = fields.Boolean(string="Cuenta de movimiento",default= False)