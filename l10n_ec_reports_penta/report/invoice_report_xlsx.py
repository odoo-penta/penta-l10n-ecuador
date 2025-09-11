# -*- coding: utf-8 -*-
from odoo import models

class PentalabInvoiceReportXlsx(models.AbstractModel):
    _name = "report.l10n_ec_reports_penta.invoice_report_xlsx"
    _description = "XLSX - Reporte de Facturas"
    _inherit = "report.report_xlsx.abstract"

    def generate_xlsx_report(self, workbook, data, objs):
        sheet = workbook.add_worksheet("Facturas")

        headers = [
            "Empresa","Fecha factura","Fecha contable","Número","Diario","Tipo doc","Referencia",
            "N° pedido","N° autorización","Identificación","Contacto",
            "Términos de pago","Método de pago",
            "Ref. interna","Producto","Categoría Padre","Categoría",
            "Cantidad facturada","Precio unitario","Impuestos",
            "Subtotal","Total","Moneda"
        ]
        for c, h in enumerate(headers):
            sheet.write(0, c, h)

        domain = data.get("domain", [])
        lines = self.env["pentalab.invoice.report.line"].search(domain, order="date, move_name, id")

        row = 1
        for l in lines:
            vals = [
                l.company_name, str(l.invoice_date or ""), str(l.date or ""), l.move_name, l.journal_name,
                l.doc_type_name, l.ref, l.purchase_order_name, l.auth_number, l.partner_vat,
                l.partner_name, l.payterm_name, l.paymethod_name,
                l.default_code, l.product_name, l.parent_categ_name, l.categ_name,
                l.quantity, l.price_unit, l.taxes,
                l.price_subtotal, l.price_total, l.currency_id and l.currency_id.name or ""
            ]
            for c, v in enumerate(vals):
                sheet.write(row, c, v)
            row += 1