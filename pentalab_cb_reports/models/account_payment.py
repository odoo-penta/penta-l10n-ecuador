from odoo import models, api, fields
from odoo.exceptions import ValidationError


class account_payment_module(models.Model):
    _inherit = 'account.payment'

    partner_id = fields.Many2one('res.partner')

    move_line_ids = fields.Many2many(
        comodel_name="account.move.line", 
        # domain=[('display_type', '=', 'payment_term'), ('amount_residual_currency', '>', 0),('partner_id','=',partner_id.id)],
        # domain=lambda self: self._get_move_line_domain(),
        string="Cuotas de Facturas"
    )

    @api.onchange('move_line_ids')
    def _onchange_move_line_ids(self):
        # Obtener los partner_id de las líneas seleccionadas
        partner_ids = {move_line.partner_id.id for move_line in self.move_line_ids if move_line.partner_id}

        # Verificar si todos los partner_id son iguales
        if len(partner_ids) > 1:
            # Si hay más de un partner_id, significa que no son todos iguales
            raise ValidationError("Los clientes de las líneas seleccionadas deben ser iguales.")

    journal_code = fields.Char(compute='_compute_journal_code', store=True)

    @api.depends('journal_id')
    def _compute_journal_code(self):
        for record in self:
            record.journal_code = record.journal_id.code if record.journal_id else ''