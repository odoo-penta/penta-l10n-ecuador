from odoo import models, fields

ACCOUNT_MOVE_MODEL = 'account.move'

class AccountMoveInventoryReportAction(models.Model):
    _inherit = ACCOUNT_MOVE_MODEL
    
    valuation_moves_ids = fields.Many2many(
        comodel_name='account.move',
        string='Asientos de valuación',
        compute='_compute_valuation_moves',
        store=False,
    )


    def _compute_valuation_moves(self):
        for move in self:
            purchase_orders = self.env['purchase.order'].search([
                ('name', '=', move.invoice_origin)
            ])
            pickings = purchase_orders.mapped('picking_ids')
            valuation_layers = self.env['stock.valuation.layer'].search([
                ('stock_move_id.picking_id', 'in', pickings.ids),
                ('product_id', 'in', move.invoice_line_ids.mapped('product_id').ids),
            ])
            move.valuation_moves_ids = valuation_layers.mapped('account_move_id')


    def _get_report_values(self, docids, data=None):
        docs = self.env[ACCOUNT_MOVE_MODEL].browse(docids)
        for move in docs:
            # Buscar órdenes de compra desde el origen
            purchase_orders = self.env['purchase.order'].search([
                ('name', '=', move.invoice_origin)
            ])

            # Obtener recepciones
            pickings = purchase_orders.mapped('picking_ids')

            # Obtener capas de valuación relacionadas
            valuation_layers = self.env['stock.valuation.layer'].search([
                ('stock_move_id.picking_id', 'in', pickings.ids),
                ('product_id', 'in', move.invoice_line_ids.mapped('product_id').ids),
            ])

            # Guardar movimientos de valuación como campo temporal
            move.valuation_moves_ids = valuation_layers.mapped('account_move_id')

        return {
            'doc_model': ACCOUNT_MOVE_MODEL,
            'docs': docs,
        }