
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

ABC_CLASSIFICATION_SELECTION = [
    ('A', 'A'), ('B', 'B'), ('C', 'C'),
    ('D', 'D'), ('E', 'E'), ('F', 'F')
]

class ProductAbcHistoryLine(models.Model):
    _name = 'product.abc.history.line'
    _description = 'Historial ABC - Línea de Producto'
    _order = 'default_code, id'

    batch_id = fields.Many2one('product.abc.history.batch', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='batch_id.company_id', store=True)
    year = fields.Integer(related='batch_id.year', store=True)
    month = fields.Integer(related='batch_id.month', store=True)

    product_id = fields.Many2one('product.product', string='Producto', index=True)
    default_code = fields.Char(string='Referencia Interna', index=True)

    annual_sales_qty = fields.Float(string='Cantidad vendida anual')
    abc_classification = fields.Selection(ABC_CLASSIFICATION_SELECTION, string='ABC')

    _sql_constraints = [
        ('uniq_batch_product', 'unique(batch_id, product_id)',
         'El producto ya está guardado en este historial.')
    ]
