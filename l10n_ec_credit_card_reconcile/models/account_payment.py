from odoo import models, fields, api

class PosPayment(models.Model):
    _inherit = 'account.payment'

    # Nuevo campo tipo selección basado en los registros de account.cards
    card_id = fields.Many2one('account.cards', string='Tarjeta relacionada', compute='_compute_card_id', store=True)

    # def _get_card_id(self):
    #     """Retorna las tarjetas de crédito activas para el campo Selection"""
    #     return [(card.id, card.name) for card in self.env['account.cards'].search([('active', '=', True)])]
    

    @api.depends('x_studio_tarjeta')
    def _compute_card_id(self):
        for record in self:

            if record.x_studio_tarjeta:
                tarjetas = self.env['account.cards'].search([
                    ('name', 'ilike', record.x_studio_tarjeta),
                    ('active', '=', True)
                ])

                if tarjetas:
                    record.card_id = tarjetas[0]
                else:
                    record.card_id = False
            else:
                record.card_id = False


