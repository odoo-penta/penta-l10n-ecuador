# l10n_ec_reports_penta — Reportes Pentalab (Ecuador)

Este módulo provee varios reportes y exportaciones (XLSX / QWeb-PDF) usados en la contabilidad.

---

## Índice rápido

- Ventas A1 (XLSX)
- Compras A2 (XLSX)
- Retenciones Compras A3 (XLSX)
- Retenciones Ventas (XLSX)
- UAFE (ZIP con varios XLSX)
- Anexo de Compras (vista lista / export_xlsx)
- Cobros por Ventas (lista / PDF)
- Pagos por Compras (lista / PDF)
- Inventario (vistas list / export XLSX desde wizard)
- Reporte Asiento Contable / Valuación (QWeb PDF)
- Reporte Consolidado de Despachos (lista)

---

## Detalle de reportes y campos

1) Ventas A1 (wizard: `report.sales.a1.wizard`)

- Tipo: XLSX
- Archivo: generado por `wizard/report_sales_a1_wizard.py`
- Columnas principales:
  - # (contador)
  - TIPO DE COMPROBANTE — `invoice.l10n_latam_document_type_id.name`
  - TIPO DE IDENTIFICACIÓN — `invoice.partner_id.l10n_latam_identification_type_id.name`
  - IDENTIFICACIÓN — `invoice.partner_id.vat`
  - RAZÓN SOCIAL — `invoice.partner_id.complete_name`
  - PARTE RELACIONADA — `partner.l10n_ec_related_party` (SI/NO)
  - TIPO DE SUJETO — derivado de `partner.company_type`
  - NRO. DE DOCUMENTO — `invoice.name`
  - NRO. AUTORIZACIÓN — `invoice.l10n_ec_authorization_number`
  - FECHA EMISIÓN — `invoice.invoice_date`
  - Columnas dinámicas por `account.tax.group` con `show_report=True`:
    - BASE <GRUPO>
    - MONTO <GRUPO>
  - TOTAL VENTA — `invoice.amount_total`
  - Varios campos de retenciones (RET 10%, RET 20%, etc.) y códigos/fechas/autorizaciones de retención
  - POSICIÓN FISCAL — `invoice.fiscal_position_id.name`
  - DIARIO CONTABLE — `invoice.journal_id.name`
  - CTA. CONTABLE — código de cuenta detectado en líneas (`liability_payable`)
  - REFERENCIA — `invoice.ref`

2) Compras A2 (wizard: `report.purchase.a2.wizard`)

- Tipo: XLSX
- Archivo: `wizard/report_purchase_a2_wizard.py`
- Columnas principales:
  - #, SUSTENTO TRIBUTARIO (extraído desde `tax.l10n_ec_code_taxsupport` en líneas)
  - TIPO DE IDENTIFICACIÓN, IDENTIFICACIÓN, RAZÓN SOCIAL (partner)
  - TIPO DE CONTRIBUYENTE — `partner.l10n_ec_taxpayer_type_id.name`
  - PARTE RELACIONADA, TIPO DE SUJETO
  - TIPO DE COMPROBANTE — `invoice.l10n_latam_document_type_id.name`
  - NRO DE FACTURA, AUTORIZACIÓN, FECHA EMISIÓN, FECHA CONTABILIZACIÓN
  - Columnas dinámicas BASE/MONTO por `account.tax.group` (como en A1)
  - COD RET IVA, RET 10%/20%/... (montos por porcentaje), COD RET FUENTE
  - BASE IMP, PORCENTAJE DE RETENCIÓN FUENTE, VALOR RETENIDO
  - COMPROBANTE DE RETENCIÓN, AUT. RET., FECHA DE RETENCIÓN
  - POSICIÓN FISCAL, PAÍS DE PAGO, PARAÍSO FISCAL, DIARIO CONTABLE, FORMATO PAGO 1
  - CTA. CONTABLE, REFERENCIA

3) Retenciones Compras A3 (wizard: `report.retentions.a3.wizard`)

- Tipo: XLSX
- Columnas:
  - #, FECHA DE EMISIÓN, DIARIO, NÚMERO DE RETENCIÓN
  - RUC, RAZÓN SOCIAL, AUTORIZACIÓN SRI
  - BASE IMPONIBLE, VALOR RETENIDO, PORCENTAJE DE RETENCIÓN
  - CÓDIGO BASE, CÓDIGO APLICADO, CÓDIGO ATS
  - NRO DE DOCUMENTO (factura origen), FECHA EMISIÓN FACTURA PROVEEDOR
  - CUENTA CONTABLE (línea asociada al impuesto)

4) Retenciones Ventas (wizard: `report.sales.withholding.wizard`)

- Tipo: XLSX
- Columnas:
  - #, FECHA DE EMISIÓN (retención), DIARIO, NUMERO DE RETENCIÓN
  - RUC, RAZÓN SOCIAL, AUTORIZACIÓN SRI
  - BASE IMPONIBLE, VALOR RETENIDO, PORCENTAJE
  - TIPO (normalizado a IVA/Fuente), CODIGO DECLARACION FISCAL (tax_tag), NRO FACTURA, FECHA FACTURA

5) UAFE (wizard: `report.uafe.wizard`)

- Tipo: ZIP con varios XLSX (DETALLECLIENTE.xlsx, DETALLEOPERACION.xlsx, DETALLETRANSACCION.xlsx, CABECERA.xlsx)
- Campos/archivos:
  - CABECERA.xlsx → totales y conteos del reporte (TOTAL_REG_CLIENTES, TOTAL_REG_OPERACIONES, etc.)
  - DETALLECLIENTE.xlsx → columnas por cliente: tipo persona, tipo id, ID_CLIENTE (vat), nombre, dirección, códigos de provincia/cantón/parroquia, ingreso_cliente
  - DETALLEOPERACION.xlsx → detalle por operación (incluye NUMERO_OPERACION, FECHA_OPERACION, datos del producto como CHASIS/N LOTE, MARCA, MODELO, CILINDRAJE)
  - DETALLETRANSACCION.xlsx → detalle de transacciones y montos por tipo de pago (efectivo/cheque/tarjeta/valores/bienes)

6) Anexo de Compras (vista/acción: `pentalab.invoice.report.wizard` → modelo `pentalab.invoice.report.line`)

- Tipo: Vista lista con `export_xlsx="1"` (archivo: `views/invoice_report_views.xml`)
- Campos visibles / exportables en la vista:
  - company_id, invoice_date, date, move_name, journal_id, doc_type_name, ref, purchase_order_name,
  - auth_number, partner_vat, partner_id, payterm_name, paymethod_name, default_code, product_name,
  - parent_categ_name, categ_name, quantity, price_unit, taxes, price_subtotal, price_total, currency_id

7) Cobros por Ventas (vista `cobros.por.ventas`)

- Tipo: Lista exportable y PDF QWeb
- Campos: x_date, x_journal, x_move_name, x_reference, x_account, x_partner_name, x_tag, x_debit, x_credit

8) Pagos por Compras (vista `pagos.por.compras`)

- Tipo: Lista exportable y PDF QWeb
- Campos: x_date, x_journal, x_move_name, x_reference, x_account, x_partner_name (Proveedor), x_tag, x_credit, x_debit, x_account_type, x_payment_type

9) Inventario / Stock (vistas `stock.quant.aggregated` y `stock.quant`)

- Tipo: List views con botón para exportar XLSX
- Campos (ejemplos): warehouse_id, location_parent_id, default_code, product_name, product_line, product_group, product_category, quantity, standard_price, list_price, store_location, packaging_name, attributes_and_variants

10) Asiento contable / Valuación (QWeb PDF, `report_account_move_inventory_document`)

- Tipo: QWeb PDF para `account.move`
- Campos en plantilla:
  - Cabecera: `o.name`, `o.ref`, `o.date`, `o.journal_id`
  - Líneas: `jeline.account_id` (cuenta), `jeline.partner_id`, `jeline.name` (descripción), `jeline.debit`, `jeline.credit`
  - Totales: sumas de débito y crédito

11) Reporte Consolidado de Despachos (`stock.picking.report`)

- Tipo: vista lista / acción servidor (genera reporte)
- Campos: origin_location, destination_location, company_vat, carrier, vehicle_plate, driver_name, document_date, document_number, waybill_number, transfer_reason, customer_name, total_quantity, total_weight

---