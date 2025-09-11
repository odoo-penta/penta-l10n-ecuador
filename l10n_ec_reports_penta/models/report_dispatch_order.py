# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class DispatchReport(models.TransientModel):
    _name = 'dispatch.report'
    _description = 'Reporte de Despachos'

    picking_id = fields.Many2one('stock.picking', string='Egreso de Bodega')
    order_id = fields.Many2one('sale.order', string='Orden de Venta')
    invoice_id = fields.Many2one('account.move', string='Factura')
    user_id = fields.Many2one('res.users', string='Vendedor')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    vat = fields.Char(string='Identificación Fiscal')
    street = fields.Char(string='Calle')
    street2 = fields.Char(string='Calle 2')
    city = fields.Char(string='Ciudad')
    state_id = fields.Many2one('res.country.state', string='Estado')
    order_name = fields.Char(string='Número Orden Venta')
    order_date = fields.Datetime(string='Fecha Orden Venta')
    picking_name = fields.Char(string='Número Egreso')
    picking_date = fields.Datetime(string='Fecha del Picking')
    invoice_number = fields.Char(string='Número Factura')
    default_code = fields.Char(string='Referencia Interna')
    product_id = fields.Many2one('product.product', string='Producto')
    product_variant = fields.Char(string='Atributos y Variantes')
    weight = fields.Float(string='Peso Total')
    location_id = fields.Many2one('stock.location', string='Ubicación')
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén')
    product_packaging_id = fields.Many2one(
        'product.packaging',
        string='Embalaje'
    )

    @api.model
    def action_generate_report(self):
        """Genera el reporte de despachos desde stock.picking."""
        _logger.info("Iniciando la generación del Reporte de Despachos")
        try:
            self.search([]).unlink()

            pickings = self.env['stock.picking'].search([('state', '=', 'done')])
            _logger.info(f"Se encontraron {len(pickings)} órdenes de despacho en estado 'done'")

            if not pickings:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Reporte Vacío',
                        'message': 'No hay órdenes de despacho completadas para mostrar.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            data_to_create = []

            for picking in pickings:
                sale_order = picking.sale_id
                invoice = self.env['account.move'].search([('invoice_origin', '=', sale_order.name)], limit=1) if sale_order else False
                partner = picking.partner_id

                for move_line in picking.move_line_ids:
                    product = move_line.product_id

                    # ===== Determinar Embalaje =====
                    packaging_rec = False
                    # Preferir el embalaje elegido en la línea de venta (si viene de venta)
                    sale_line = getattr(move_line.move_id, 'sale_line_id', False)
                    if sale_line and getattr(sale_line, 'product_packaging_id', False):
                        packaging_rec = sale_line.product_packaging_id
                    # Como fallback, si existiera un product_packaging_id en el move (personalización)
                    elif hasattr(move_line.move_id, 'product_packaging_id') and move_line.move_id.product_packaging_id:
                        packaging_rec = move_line.move_id.product_packaging_id

                    data_to_create.append({
                        'picking_id': picking.id,
                        'order_id': sale_order.id if sale_order else False,
                        'invoice_id': invoice.id if invoice else False,
                        'user_id': sale_order.user_id.id if sale_order else False,
                        'partner_id': partner.id,
                        'vat': partner.vat,
                        'street': partner.street,
                        'street2': partner.street2,
                        'city': partner.city,
                        'state_id': partner.state_id.id if partner.state_id else False,
                        'order_name': sale_order.name if sale_order else '',
                        'order_date': sale_order.date_order if sale_order else False,
                        'picking_name': picking.name,
                        'picking_date': picking.date_done,
                        'invoice_number': invoice.name if invoice else '',
                        'default_code': product.default_code,
                        'product_id': product.id,
                        'product_variant': product.product_template_attribute_value_ids._get_combination_name() if product.product_template_attribute_value_ids else '',
                        'weight': move_line.quantity * product.weight if product.weight else 0.0,
                        'location_id': move_line.location_id.id,
                        'warehouse_id': picking.picking_type_id.warehouse_id.id if picking.picking_type_id.warehouse_id else False,
                        'product_packaging_id': packaging_rec.id if packaging_rec else False,
                    })

            if not data_to_create:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Reporte Vacío',
                        'message': 'No se generaron datos para el reporte.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            self.create(data_to_create)
            _logger.info(f"Se crearon {len(data_to_create)} registros para el reporte de despachos")

            return {
                'type': 'ir.actions.act_window',
                'name': 'Reporte de Despachos',
                'res_model': 'dispatch.report',
                'view_mode': 'list',
                'target': 'current',
            }

        except Exception as e:
            _logger.error(f"Error generando el reporte de despachos: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error en el Reporte',
                    'message': f'Se produjo un error al generar el reporte: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
