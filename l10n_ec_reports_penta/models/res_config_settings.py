
from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sales_amount_report_uafe = fields.Monetary(
        related='company_id.sales_amount_report_uafe',
        string='Sales amount reported by UAFE', readonly=False,
        help='We specify the amount that customer purchases must reach to be considered in the UAFE report.')
    
    #Pagos 
    payment_prepared_by_id = fields.Many2one(
        related='company_id.payment_prepared_by_id',
        comodel_name='res.users',
        readonly=False,
        string='Pagos - Elaborado por'
    )
    payment_reviewed_by_id = fields.Many2one(
        related='company_id.payment_reviewed_by_id',
        comodel_name='res.users',
        readonly=False,
        string='Pagos - Revisado por'
    )

    # Asiento
    move_prepared_by_id = fields.Many2one(
        related='company_id.move_prepared_by_id',
        comodel_name='res.users',
        readonly=False,
        string='Asiento - Elaborado por'
    )
    move_reviewed_by_id = fields.Many2one(
        related='company_id.move_reviewed_by_id',
        comodel_name='res.users',
        readonly=False,
        string='Asiento - Revisado por'
    )

    # Pagos en lote
    batch_payment_prepared_by_id = fields.Many2one(
        related='company_id.batch_payment_prepared_by_id',
        comodel_name='res.users',
        readonly=False,
        string='Pagos en lote - Elaborado por'
    )
    batch_payment_reviewed_by_id = fields.Many2one(
        related='company_id.batch_payment_reviewed_by_id',
        comodel_name='res.users',
        readonly=False,
        string='Pagos en lote - Revisado por'
    )