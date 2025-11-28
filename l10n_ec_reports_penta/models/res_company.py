
from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    sales_amount_report_uafe = fields.Monetary(
        string='Sales amount reported by UAFE',
        currency_field='currency_id',
        help='We specify the amount that customer purchases must reach to be considered in the UAFE report.')
    
        # --- Personal de autorización por empresa ---
    # Pagos
    payment_prepared_by_id = fields.Many2one(
        'res.users', string='Pagos - Elaborado por',
        help='Usuario responsable de elaborar pagos.'
    )
    payment_reviewed_by_id = fields.Many2one(
        'res.users', string='Pagos - Revisado por',
        help='Usuario responsable de revisar pagos.'
    )

    # Asiento
    move_prepared_by_id = fields.Many2one(
        'res.users', string='Asiento - Elaborado por',
        help='Usuario responsable de elaborar asientos contables.'
    )
    move_reviewed_by_id = fields.Many2one(
        'res.users', string='Asiento - Revisado por',
        help='Usuario responsable de revisar asientos contables.'
    )

    # Pagos en lote
    batch_payment_prepared_by_id = fields.Many2one(
        'res.users', string='Pagos en lote - Elaborado por',
        help='Usuario responsable de elaborar pagos en lote.'
    )
    batch_payment_reviewed_by_id = fields.Many2one(
        'res.users', string='Pagos en lote - Revisado por',
        help='Usuario responsable de revisar pagos en lote.'
    )


    # Retenciones
    retention_prepared_by_id = fields.Many2one(
        'res.users', string='Retenciones - Elaborado por',
        help='Usuario responsable de elaborar retenciones.'
    )
    retention_reviewed_by_id = fields.Many2one(
        'res.users', string='Retenciones - Revisado por',
        help='Usuario responsable de revisar retenciones.'
    )
    retention_delivered_by_id = fields.Many2one(
        'res.users', string='Retenciones - Entregue conforme',
        help='Usuario responsable de entregar comformes de retenciones.'
    )
