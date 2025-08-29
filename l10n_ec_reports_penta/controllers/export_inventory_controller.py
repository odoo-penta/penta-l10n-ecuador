from odoo import http
from odoo.http import request
import io
import xlsxwriter
from dateutil.relativedelta import relativedelta
from datetime import datetime

class InventoryExportController(http.Controller):

    @http.route('/inventory_export_xlsx', type='http', auth='user')
    def export_inventory_xlsx(self, month, year, **kwargs):
        start = datetime(int(year), int(month), 1)
        print('Fecha de inicio:', start)
        end = (start + relativedelta(months=1))
        print('Fecha de fin:', end)

        records = request.env['stock.quant.aggregated'].sudo().search([
            ('in_date', '>=', start),
            ('in_date', '<', end),
            ('location_usage', '=', 'internal'),
        ])

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        sheet = workbook.add_worksheet("Inventario")

        headers = [
            "Almacén", "Nombre corto", "Referencia interna", "Producto",
            "Línea", "Grupo", "Artículo", "Cantidad a la mano", "Costo", "Precio", "Fecha de ingreso"
        ]
        for col, header in enumerate(headers):
            sheet.write(0, col, header)

        row = 1
        for rec in records:
            sheet.write(row, 0, rec.warehouse_id.name if rec.warehouse_id else '')
            sheet.write(row, 1, rec.location_parent_id.name if rec.location_parent_id.name else '')
            sheet.write(row, 2, rec.default_code or '')
            sheet.write(row, 3, rec.product_name or '')
            sheet.write(row, 4, rec.product_line or '')
            sheet.write(row, 5, rec.product_group or '')
            sheet.write(row, 6, rec.product_category or '')
            sheet.write(row, 7, rec.quantity)
            sheet.write(row, 8, rec.standard_price or 0.0)
            sheet.write(row, 9, rec.list_price or 0.0)
            sheet.write(row, 9, rec.in_date or '')
            row += 1

        workbook.close()
        output.seek(0)
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="inventario_{month}_{year}.xlsx"')
            ]
        )