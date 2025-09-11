# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CreditCardReconcileLine(models.Model):
    _name = 'credit.card.reconcile.line'
    _description = 'Líneas de Conciliación de Tarjetas de Crédito'

    credit_card_reconcile_id = fields.Many2one(
        'credit.card.reconcile',
        string='Conciliación'
    )
    move_line_id = fields.Many2one('account.move.line', string='Move Line')
    lot_number = fields.Char(string='Número de Lote')
    credit_card_voucher_number = fields.Char(string='Voucher Number')
    credit_card_type_id = fields.Many2one('account.cards', string='Tipo de Tarjeta')
    paid_amount = fields.Float(string='Total Pagado')
    payment_date = fields.Date(string='Fecha de Pago')
    total_deposit = fields.Float(string='Total Depositado')
    income_amount = fields.Float(string='Total Ret. Renta')
    vat_amount = fields.Float(string='Total Ret. IVA')
    commission = fields.Float(string='Total Comisión')
    bank_voucher_number = fields.Char(string='Número de Voucher Bancario')

    withhold_sequential = fields.Char(string='Sec. de Retención')
    credit_card_withhold_id = fields.Many2one('account.move', string='Withhold')
    withhold_state = fields.Selection([
        ('done', 'Done'),
        ('pending', 'Pending')
    ], string='Estado Ret.')
    
    invoice_supplier_sequential = fields.Char(string="Sec. Factura Comisión")
    invoice_supplier_id = fields.Many2one('account.move', string="Factura de Comisión")
    invoice_supplier_state = fields.Selection([
        ('done', 'Done'),
        ('pending', 'Pending')
    ], string="Estado Factura", default='pending')
    
    credit_card_reconcile_id = fields.Many2one('credit.card.reconcile', string="Conciliación")

    # Related desde el modelo padre
    fecha_corte = fields.Date(related='credit_card_reconcile_id.fecha_corte', store=True)
    diario_id = fields.Many2one(related='credit_card_reconcile_id.diario_id', store=True)
    banco_destino_id = fields.Many2one(related='credit_card_reconcile_id.banco_destino_id', store=True)

    payment_id = fields.Many2one('account.payment', string="Pago relacionado", store=True)

    payment_date = fields.Date(string="Fecha de pago", compute="_compute_payment_fields", store=True)
    used_card = fields.Selection(
        selection=[
            ("AMERICAN EXPRESS", "AMERICAN EXPRESS"),
            ("DINERS CLUB", "DINERS CLUB"),
            ("DISCOVER (DIFERIDO)", "DISCOVER (DIFERIDO)"),
            ("DISCOVER (CORRIENTE -DEBITO)", "DISCOVER (CORRIENTE -DEBITO)"),
            ("MILES (DIFERIDO)", "MILES (DIFERIDO)"),
            ("MILES (CORRIENTE - DEBITO)", "MILES (CORRIENTE - DEBITO)"),
            ("VISA - MASTER AUSTRO (DIFERIDO)", "VISA - MASTER AUSTRO (DIFERIDO)"),
            ("VISA - MASTER AUSTRO (CORRIENTE - DEBITO)", "VISA - MASTER AUSTRO (CORRIENTE - DEBITO)"),
            ("VISA - MASTER BOLIVARIANO (DIFERIDO)", "VISA - MASTER BOLIVARIANO (DIFERIDO)"),
            ("VISA - MASTER BOLIVARIANO (CORRIENTE - DEBITO)", "VISA - MASTER BOLIVARIANO (CORRIENTE - DEBITO)"),
            ("VISA - MASTER GUAYAQUIL (DIFERIDO)", "VISA - MASTER GUAYAQUIL (DIFERIDO)"),
            ("VISA - MASTER GUAYAQUIL (CORRIENTE - DEBITO)", "VISA - MASTER GUAYAQUIL (CORRIENTE - DEBITO)"),
            ("VISA - MASTER INTERNACIONAL", "VISA - MASTER INTERNACIONAL"),
            ("VISA LOJA (DIFERIDO)", "VISA LOJA (DIFERIDO)"),
            ("VISA - MASTER LOJA (CORRIENTE - DEBITO)", "VISA - MASTER LOJA (CORRIENTE - DEBITO)"),
            ("VISA - MASTER MACHALA (DIFERIDO)", "VISA - MASTER MACHALA (DIFERIDO)"),
            ("VISA - MASTER MACHALA (CORRIENTE - DEBITO)", "VISA - MASTER MACHALA (CORRIENTE - DEBITO)"),
            ("VISA - MASTER PACIFICO (DIFERIDO)", "VISA - MASTER PACIFICO (DIFERIDO)"),
            ("VISA - MASTER PACIFICO (CORRIENTE - DEBITO)", "VISA - MASTER PACIFICO (CORRIENTE - DEBITO)"),
            ("VISA - MASTER PICHINCHA (DIFERIDO)", "VISA - MASTER PICHINCHA (DIFERIDO)"),
            ("VISA - MASTER PICHINCHA (CORRIENTE - DEBITO)", "VISA - MASTER PICHINCHA (CORRIENTE - DEBITO)"),
            ("VISA - MASTER PRODUBANCO (DIFERIDO)", "VISA - MASTER PRODUBANCO (DIFERIDO)"),
            ("VISA - MASTER PRODUBANCO (CORRIENTE - DEBITO)", "VISA - MASTER PRODUBANCO (CORRIENTE - DEBITO)"),
            ("VISA - MASTER RUMIÑAHUI (DIFERIDO)", "VISA - MASTER RUMIÑAHUI (DIFERIDO)"),
            ("VISA - MASTER RUMIÑAHUI (CORRIENTE - DEBITO)", "VISA - MASTER RUMIÑAHUI (CORRIENTE - DEBITO)"),
            ("VISA TITANIUM (CORRIENTE - DEBITO)", "VISA TITANIUM (CORRIENTE - DEBITO)"),
            ("VISA - MASTER COOP JEP (DIFERIDO)", "VISA - MASTER COOP JEP (DIFERIDO)"),
            ("VISA - MASTER COOP JEP (CORRIENTE - DEBITO)", "VISA - MASTER COOP JEP (CORRIENTE - DEBITO)"),
            ("VISA OTRAS COOPERATIVAS", "VISA OTRAS COOPERATIVAS"),
            ("UNION PAY", "UNION PAY"),
            ("BANCOS AMERICANOS", "BANCOS AMERICANOS"),
            ("MASTER INTERNACIONAL", "MASTER INTERNACIONAL"),
            ("VISA TITANIUM (DIFERIDO)", "VISA TITANIUM (DIFERIDO)"),
        ],
        string="Tarjeta usada",
        compute="_compute_payment_fields",
        store=True
    )

    number_months = fields.Selection(
        selection=[
            ('0', '0'),
            ('3', '3'),
            ('6', '6'),
            ('9', '9'),
            ('12', '12'),
            ('18', '18'),
            ('24', '24'),
            ('36', '36'),
            ('48', '48'),
            ('60', '60'),
        ],
        string="Meses",
        compute="_compute_payment_fields",
        store=True
    )

    card_id = fields.Many2one(
        comodel_name='account.cards',
        string="Tarjeta",
        compute="_compute_payment_fields",
        store=True
    )

    @api.depends('payment_id')
    def _compute_payment_fields(self):
        for rec in self:
            rec.payment_date = rec.payment_id.date if rec.payment_id else False
            rec.used_card = rec.payment_id.used_card if rec.payment_id else False
            rec.number_months = rec.payment_id.number_months if rec.payment_id else False
            rec.card_id = rec.payment_id.card_id if rec.payment_id else False
