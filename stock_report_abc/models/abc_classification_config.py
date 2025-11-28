# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date
from dateutil.relativedelta import relativedelta
class AbcClassificationConfig(models.Model):
    _name = 'abc.classification.config'
    _description = 'Configuración de Clasificación ABC'

    
    name = fields.Char(string='Nombre', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    
    rating_a = fields.Integer(string='A', default=6, help='Meses con ventas para clasificación A')
    rating_b = fields.Integer(string='B', default=4, help='Meses con ventas para clasificación B')
    rating_c = fields.Integer(string='C', default=2, help='Meses con ventas para clasificación C')
    rating_d = fields.Integer(string='D', default=1, help='Meses con ventas para clasificación D')

    # Nuevo: Año de referencia
    year = fields.Integer(string="Año", store=True,readonly=True)
    month = fields.Selection(
        [
            ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'),
            ('4', 'Abril'), ('5', 'Mayo'), ('6', 'Junio'),
            ('7', 'Julio'), ('8', 'Agosto'), ('9', 'Septiembre'),
            ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
        ],
        string="Mes",
        store=True,
        readonly=True
    )

    @api.model
    def cron_update_reference_period(self):
        today = fields.Date.context_today(self)
        ref_date = today.replace(day=1) - relativedelta(days=1)
        for company in self.env.companies:
            cfgs = self.with_company(company).sudo().env['abc.classification.config'].search([
                ('company_id', '=', company.id),
            ])
            cfgs.write({'year': ref_date.year, 'month': str(ref_date.month)})