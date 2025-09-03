# -*- coding: utf-8 -*-
from odoo import models, fields

class PentaBankDays(models.Model):
    _name = 'penta.bank.days'
    _description = 'Días Bancarios para Métodos de Pago'

    pos_payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='Método de Pago POS',
        required=True
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=True
    )
    payment_type = fields.Selection(
        selection=[
            ('Débito', 'Débito'),
            ('Corriente', 'Corriente'),
            ('Diferido con interés', 'Diferido con Interés'),
            ('Diferido sin interés', 'Diferido sin Interés')
        ],
        string='Tipo de Pago',
        required=True
    )
    number_of_months = fields.Selection(
        selection=[
            ('0', '0 meses'),
            ('3', '3 meses'),
            ('6', '6 meses'),
            ('9', '9 meses'),
            ('12', '12 meses'),
            ('18', '18 meses'),
            ('24', '24 meses'),
            ('36', '36 meses'),
            ('48', '48 meses'),
            ('60', '60 meses'),
        ],
        string='Número de Meses',
        required=True,
        default='0'
    )
    number_of_days = fields.Integer(
        string='Número de Días',
        required=True,
        default=0
    )
