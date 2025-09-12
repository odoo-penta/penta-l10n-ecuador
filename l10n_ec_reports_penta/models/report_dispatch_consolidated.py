from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class StockPickingReport(models.TransientModel):
    _name = 'stock.picking.report'
    _description = 'Consolidated Dispatch Orders Report'

    origin_location = fields.Char(string='Ubicación de Origen')
    destination_location = fields.Char(string='Ubicación de Destino')
    company_vat = fields.Char(string='N° Identificación Fiscal')
    carrier = fields.Char(string='Transportista')
    vehicle_plate = fields.Char(string='Placa del Vehículo')
    driver_name = fields.Char(string='Nombre del Conductor')
    document_date = fields.Datetime(string='Fecha del Documento')
    document_number = fields.Char(string='Número del Documento')
    waybill_number = fields.Char(string='Guía de Remisión')
    transfer_reason = fields.Char(string='Motivo del Traslado')
    customer_name = fields.Char(string='Nombre del Cliente')
    total_quantity = fields.Float(string='Cantidad Total')
    total_weight = fields.Float(string='Peso Total')
    picking_id = fields.Many2one('stock.picking', string='Orden de Despacho')

    @api.model
    def action_generate_report(self):
        _logger.info("Iniciando la generación del reporte de despachos")
        try:
            # Buscar órdenes de despacho en estado 'done'
            pickings = self.env['stock.picking'].search([('state', '=', 'done')])
            _logger.info(f"Se encontraron {len(pickings)} órdenes de despacho en estado 'done'")

            if not pickings:
                _logger.warning("No se encontraron órdenes de despacho en estado 'done'")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Reporte Vacío',
                        'message': 'No hay órdenes de despacho completadas para mostrar en el reporte.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            report_data = []
            for picking in pickings:
                try:
                    # Verificar líneas de movimiento
                    move_lines = picking.move_line_ids
                    _logger.info(f"Procesando picking {picking.name} con {len(move_lines)} líneas de movimiento")

                    total_quantity = sum(move_line.quantity for move_line in move_lines) if move_lines else 1.0

                    # Usar 'weight_bulk' para el peso
                    total_weight = picking.weight_bulk if hasattr(picking, 'weight_bulk') else 0.0

                    vals = {
                        'origin_location': picking.picking_type_id.warehouse_id.name or 'Sin almacén',
                        'destination_location': picking.partner_id.city or 'Sin ciudad',
                        'company_vat': picking.company_id.vat or 'Sin RUC',
                        'carrier': picking.l10n_ec_transporter_id.name or 'Sin transportista',
                        'vehicle_plate': picking.l10n_ec_plate_number or 'Sin placa',
                        'driver_name': picking.driver_name or 'Sin conductor',
                        'document_date': picking.l10n_ec_delivery_end_date,
                        'document_number': picking.name or 'Sin número',
                        'waybill_number': picking.l10n_ec_edi_document_number or 'Sin guía',
                        'transfer_reason': picking.l10n_ec_transfer_reason or 'Sin motivo',
                        'customer_name': picking.partner_id.name or 'Sin cliente',
                        'total_quantity': total_quantity,
                        'total_weight': total_weight,
                        'picking_id': picking.id,
                    }
                    report_data.append(vals)
                    _logger.info(f"Agregado picking {picking.name} con cantidad total {total_quantity} y peso total {total_weight}")
                except Exception as e:
                    _logger.error(f"Error procesando picking {picking.name}: {str(e)}")
                    continue

            if not report_data:
                _logger.warning("No se generaron datos para el reporte")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Reporte Vacío',
                        'message': 'No se generaron datos para el reporte. Verifica los logs para más detalles.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            # Limpiar registros anteriores y crear nuevos
            self.search([]).unlink()
            self.create(report_data)
            _logger.info(f"Se crearon {len(report_data)} registros para el reporte")

            action = {
                'type': 'ir.actions.act_window',
                'name': 'Reporte Consolidado de Órdenes de Despacho',
                'res_model': 'stock.picking.report',
                'view_mode': 'list',
                'target': 'current',
            }
            _logger.info(f"Devolviendo acción de ventana: {action}")
            return action
        except Exception as e:
            _logger.error(f"Error generando el reporte: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error en el Reporte',
                    'message': f'Se produjo un error al generar el reporte: {str(e)}. Verifica los logs para más detalles.',
                    'type': 'danger',
                    'sticky': True,
                }
            }