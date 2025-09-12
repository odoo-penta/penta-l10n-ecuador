# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

def _m2o(rec):
    """Devuelve el id si el record existe; si no, False."""
    return rec.exists().id if rec else False

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

    # Embalaje (product.packaging)
    product_packaging_id = fields.Many2one('product.packaging', string='Embalaje')

    @api.model
    def action_generate_report(self):
        """Genera el reporte de despachos desde stock.picking."""
        _logger.info("Iniciando la generación del Reporte de Despachos")
        try:
            # Limpia previos (modelo transiente)
            self.search([]).unlink()

            pickings = self.env['stock.picking'].search([('state', '=', 'done')])
            _logger.info("Pickings en done: %s", len(pickings))

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
                invoice = sale_order and self.env['account.move'].search(
                    [('invoice_origin', '=', sale_order.name)], limit=1
                ) or False
                partner = picking.partner_id

                for move_line in picking.move_line_ids:
                    product = move_line.product_id

                    # --- Determinar Embalaje de la línea de venta ---
                    sale_line = getattr(move_line.move_id, 'sale_line_id', False)
                    packaging_rec = False
                    if sale_line:
                        # Intenta ambos nombres de campo según versión/base
                        packaging_rec = getattr(sale_line, 'product_packaging_id', False) or \
                                        getattr(sale_line, 'packaging_id', False)
                        # Asegura que el registro exista y sea del modelo correcto
                        if packaging_rec and packaging_rec._name != 'product.packaging':
                            packaging_rec = False
                        if packaging_rec:
                            packaging_rec = packaging_rec.exists()

                    # Fallback: si has personalizado packaging en el move
                    if not packaging_rec and hasattr(move_line.move_id, 'product_packaging_id'):
                        packaging_rec = move_line.move_id.product_packaging_id.exists()

                    data_to_create.append({
                        'picking_id': _m2o(picking),
                        'order_id': _m2o(sale_order),
                        'invoice_id': _m2o(invoice),
                        'user_id': _m2o(sale_order.user_id) if sale_order else False,
                        'partner_id': _m2o(partner),
                        'vat': partner.vat,
                        'street': partner.street,
                        'street2': partner.street2,
                        'city': partner.city,
                        'state_id': _m2o(partner.state_id),
                        'order_name': sale_order.name if sale_order else '',
                        'order_date': sale_order.date_order if sale_order else False,
                        'picking_name': picking.name,
                        'picking_date': picking.date_done,
                        'invoice_number': invoice.name if invoice else '',
                        'default_code': product.default_code,
                        'product_id': _m2o(product),
                        'product_variant': product.product_template_attribute_value_ids._get_combination_name()
                            if product.product_template_attribute_value_ids else '',
                        # Si prefieres qty_done en lugar de quantity, cámbialo aquí:
                        'weight': (getattr(move_line, 'quantity', 0.0) or getattr(move_line, 'qty_done', 0.0)) * (product.weight or 0.0),
                        'location_id': _m2o(move_line.location_id),
                        'warehouse_id': _m2o(picking.picking_type_id.warehouse_id),
                        'product_packaging_id': _m2o(packaging_rec),
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
            _logger.info("Registros creados para el reporte: %s", len(data_to_create))

            return {
                'type': 'ir.actions.act_window',
                'name': 'Reporte de Despachos',
                'res_model': 'dispatch.report',
                'view_mode': 'list',
                'target': 'current',
            }

        except Exception as e:
            _logger.exception("Error generando el reporte de despachos")
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
