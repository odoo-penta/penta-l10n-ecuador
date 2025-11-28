# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date

_logger = logging.getLogger(__name__)


class ProductSold(models.Model):
    _name = 'product.sold'
    _description = 'Productos Vendidos Anteriores'
    _rec_name = 'default_code'
    _check_company_auto = True
        
    default_code = fields.Char(string='Referencia Interna', required=True)
    name = fields.Char(string='Producto', required=True)
    line = fields.Char(string='Línea', store=True)
    qty_sold_monthly = fields.Float(string='Cantidad Vendida Mensual', required=True)
    year = fields.Char(string='Año', required=True)
    month = fields.Integer(string='Mes', required=True)
    date = fields.Date(string='Fecha', compute='_compute_date', store=True)
    abc_classification = fields.Char(string='Clasificación ABC', readonly=True)

    company_id = fields.Many2one(
        'res.company', string='Empresa',
        required=True, default=lambda self: self.env.company, index=True, check_company=True
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto relacionado',
        compute='_compute_product_id',
        store=True
    )

    @api.depends('default_code')
    def _compute_product_id(self):
        for record in self:
            if record.default_code:
                product = self.env['product.product'].search(
                    [('default_code', '=', record.default_code)],
                    limit=1
                )
                record.product_id = product
            else:
                record.product_id = False

    @api.depends('year', 'month')
    def _compute_date(self):
        for record in self:
            try:
                # Convertir year a entero si es string
                year_int = int(record.year)
                # Crear un objeto date con el primer día del mes
                record.date = date(year_int, record.month, 1)
            except (ValueError, TypeError):
                record.date = False

    def calculate_abc_classification(self):
        # Buscar TODOS los registros del modelo, independientemente de la selección
        all_records = self.env['product.sold'].search([])
        
        # Verificar si hay registros
        if not all_records:
            raise UserError("No hay registros para calcular la clasificación ABC")
        
        # Agrupar por referencia y año
        grouped_products = {}
        for record in all_records:
            key = (record.default_code, record.year)
            if key not in grouped_products:
                grouped_products[key] = all_records.filtered(
                    lambda r: r.default_code == record.default_code and r.year == record.year
                )
        
        # Calcular clasificación para cada grupo
        for (default_code, year), products in grouped_products.items():
            # Calcular cantidad total vendida
            total_annual_qty = sum(product.qty_sold_monthly for product in products)
            
            # Contar meses con ventas
            months_with_sales = len(set(product.month for product in products))
            
            # Asignar clasificación ABC
            if months_with_sales >= 6 and total_annual_qty > 0:
                classification = 'A'
            elif months_with_sales >= 4 and total_annual_qty > 0:
                classification = 'B'
            elif months_with_sales >= 2 and total_annual_qty > 0:
                classification = 'C'
            elif months_with_sales >= 1 and total_annual_qty > 0:
                classification = 'D'
            else:
                classification = 'E'
            
            # Actualizar clasificación para todos los registros del producto en ese año
            products.write({'abc_classification': classification})
        
        # Notificación de éxito
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'message': f'Clasificación ABC calculada para {len(all_records)} registros.'
            }
        }