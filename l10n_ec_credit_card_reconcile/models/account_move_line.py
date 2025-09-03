from odoo import models, fields

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    credit_card_reconcile_id = fields.Many2one(
        'credit.card.reconcile',
        string='Conciliación de Tarjeta de Crédito',
        ondelete='cascade'
    )
