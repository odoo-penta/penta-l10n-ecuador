# -*- coding: utf-8 -*-
from odoo import fields, models, tools

class PentalabInvoiceReportLine(models.Model):
    _name = "pentalab.invoice.report.line"
    _description = "Anexo de Compras (Facturas publicadas de diarios de Compras)"
    _auto = False
    _rec_name = "move_name"

    # Para filtrar por ID desde el wizard
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    journal_id = fields.Many2one("account.journal", string="Diario", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Contacto", readonly=True)

    # Cabecera visibles
    company_name = fields.Char("Empresa", readonly=True)
    invoice_date = fields.Date("Fecha de factura", readonly=True)
    date = fields.Date("Fecha contable", readonly=True)
    move_name = fields.Char("Número", readonly=True)
    journal_name = fields.Char("Diario", readonly=True)
    doc_type_name = fields.Char("Tipo de documento", readonly=True)
    ref = fields.Char("Referencia", readonly=True)
    importacion = fields.Boolean("Importación", readonly=True) 
    purchase_order_name = fields.Char("N° pedido", readonly=True)
    auth_number = fields.Char("N° autorización", readonly=True)
    partner_vat = fields.Char("Identificación", readonly=True)
    partner_name = fields.Char("Contacto", readonly=True)
    payterm_name = fields.Char("Términos de pago", readonly=True)
    partner_category = fields.Char("Categoría contacto", readonly=True) 
    paymethod_name = fields.Char("Método de pago", readonly=True)
    line_name = fields.Char("Línea", readonly=True)

    # Líneas
    default_code = fields.Char("Ref. interna", readonly=True)
    product_name = fields.Char("Producto", readonly=True)
    parent_categ_name = fields.Char("Categoría Padre", readonly=True)
    categ_name = fields.Char("Categoría", readonly=True)
    quantity = fields.Float("Cantidad facturada", readonly=True)
    price_unit = fields.Monetary("Precio unitario", currency_field="currency_id", readonly=True)
    taxes = fields.Char("Impuestos", readonly=True)
    price_subtotal = fields.Monetary("Subtotal", currency_field="currency_id", readonly=True)
    price_total = fields.Monetary("Total", currency_field="currency_id", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)

    @property
    def _table_query(self):
        # SOLO asientos publicados y SOLO diarios de tipo 'purchase'
        return """
            SELECT
                aml.id AS id,

                -- IDs para filtrar
                rc.id   AS company_id,
                j.id    AS journal_id,
                rp.id   AS partner_id,

                -- Cabecera (name -> texto seguro)
                CASE WHEN pg_typeof(rc.name)::text = 'jsonb'
                    THEN COALESCE((rc.name::jsonb)->>'es_EC', (rc.name::jsonb)->>'en_US', rc.name::text)
                    ELSE rc.name::text END AS company_name,

                am.invoice_date AS invoice_date,
                am.date AS date,
                am.name AS move_name,

                CASE WHEN pg_typeof(j.name)::text = 'jsonb'
                    THEN COALESCE((j.name::jsonb)->>'es_EC', (j.name::jsonb)->>'en_US', j.name::text)
                    ELSE j.name::text END AS journal_name,

                CASE WHEN pg_typeof(ldt.name)::text = 'jsonb'
                    THEN COALESCE((ldt.name::jsonb)->>'es_EC', (ldt.name::jsonb)->>'en_US', ldt.name::text)
                    ELSE ldt.name::text END AS doc_type_name,

                am.ref AS ref,
                COALESCE(pol_po.po_names, am.invoice_origin) AS purchase_order_name,
                am.l10n_ec_authorization_number AS auth_number,
                rp.vat AS partner_vat,

                CASE WHEN pg_typeof(rp.name)::text = 'jsonb'
                    THEN COALESCE((rp.name::jsonb)->>'es_EC', (rp.name::jsonb)->>'en_US', rp.name::text)
                    ELSE rp.name::text END AS partner_name,

                -- Categorías del partner (cadena)
                pcat.partner_categories AS partner_category,

                CASE WHEN pg_typeof(apt.name)::text = 'jsonb'
                    THEN COALESCE((apt.name::jsonb)->>'es_EC', (apt.name::jsonb)->>'en_US', apt.name::text)
                    ELSE apt.name::text END AS payterm_name,

                -- Método de pago desde partner.property_inbound_payment_method_line_id
                CASE
                  WHEN pg_typeof(pmline.name)::text = 'jsonb'
                    THEN COALESCE((pmline.name::jsonb)->>'es_EC', (pmline.name::jsonb)->>'en_US', pmline.name::text)
                  ELSE pmline.name::text
                END AS paymethod_name,

                -- Línea
                pp.default_code AS default_code,

                CASE WHEN pg_typeof(ptmpl.name)::text = 'jsonb'
                    THEN COALESCE((ptmpl.name::jsonb)->>'es_EC', (ptmpl.name::jsonb)->>'en_US', ptmpl.name::text)
                    ELSE ptmpl.name::text END AS product_name,

                CASE WHEN pg_typeof(pc_parent.name)::text = 'jsonb'
                    THEN COALESCE((pc_parent.name::jsonb)->>'es_EC', (pc_parent.name::jsonb)->>'en_US', pc_parent.name::text)
                    ELSE pc_parent.name::text END AS parent_categ_name,

                CASE WHEN pg_typeof(pc.name)::text = 'jsonb'
                    THEN COALESCE((pc.name::jsonb)->>'es_EC', (pc.name::jsonb)->>'en_US', pc.name::text)
                    ELSE pc.name::text END AS categ_name,

                -- "Línea" = 3er ancestro con fallback (abuelo/padre/categoría)
                CASE
                  WHEN pg_typeof(COALESCE(pc_ggparent.name, pc_gparent.name, pc_parent.name, pc.name))::text = 'jsonb'
                    THEN COALESCE(
                      (COALESCE(pc_ggparent.name, pc_gparent.name, pc_parent.name, pc.name)::jsonb)->>'es_EC',
                      (COALESCE(pc_ggparent.name, pc_gparent.name, pc_parent.name, pc.name)::jsonb)->>'en_US',
                      COALESCE(pc_ggparent.name, pc_gparent.name, pc_parent.name, pc.name)::text
                    )
                  ELSE COALESCE(pc_ggparent.name, pc_gparent.name, pc_parent.name, pc.name)::text
                END AS line_name,

                aml.quantity AS quantity,
                aml.price_unit AS price_unit,
                taxes.names AS taxes,
                aml.price_subtotal AS price_subtotal,
                aml.price_total AS price_total,
                am.currency_id AS currency_id

            FROM account_move_line aml
            JOIN account_move am                ON am.id = aml.move_id
            LEFT JOIN res_company rc            ON rc.id = am.company_id
            LEFT JOIN account_journal j         ON j.id = am.journal_id
            LEFT JOIN l10n_latam_document_type ldt ON ldt.id = am.l10n_latam_document_type_id
            LEFT JOIN res_partner rp            ON rp.id = am.partner_id
            LEFT JOIN account_payment_term apt  ON apt.id = am.invoice_payment_term_id

            -- Método de pago (partner -> inbound payment method line)
            LEFT JOIN account_payment_method_line pmline
                   ON pmline.id = (rp.property_inbound_payment_method_line_id::jsonb ->> 'id')::integer

            -- Producto y categorías (incluye ancestros para "Línea")
            LEFT JOIN product_product pp        ON pp.id = aml.product_id
            LEFT JOIN product_template ptmpl    ON ptmpl.id = pp.product_tmpl_id
            LEFT JOIN product_category pc       ON pc.id = ptmpl.categ_id
            LEFT JOIN product_category pc_parent   ON pc_parent.id   = pc.parent_id
            LEFT JOIN product_category pc_gparent  ON pc_gparent.id  = pc_parent.parent_id
            LEFT JOIN product_category pc_ggparent ON pc_ggparent.id = pc_gparent.parent_id

            -- Categorías del partner (M2M) agregadas en una cadena
            LEFT JOIN (
                SELECT rel.partner_id AS pid,
                    string_agg(
                        CASE
                            WHEN pg_typeof(cat.name)::text = 'jsonb' THEN
                                COALESCE( (cat.name::jsonb)->>'es_EC', (cat.name::jsonb)->>'en_US', cat.name::text )
                            ELSE
                                cat.name::text
                        END,
                        ', '
                    ) AS partner_categories
                FROM res_partner_res_partner_category_rel rel
                JOIN res_partner_category cat ON cat.id = rel.category_id
                GROUP BY rel.partner_id
            ) AS pcat ON pcat.pid = rp.id

            -- Nombres de PO desde la línea de compra vinculada (name a texto)
            LEFT JOIN (
                SELECT pol.id AS line_id,
                    string_agg(DISTINCT po2.name::text, ', ') AS po_names
                FROM purchase_order_line pol
                JOIN purchase_order po2 ON po2.id = pol.order_id
                GROUP BY pol.id
            ) pol_po ON pol_po.line_id = aml.purchase_line_id

            -- Impuestos (nombres concatenados; soporta jsonb o varchar)
            LEFT JOIN (
                SELECT rel.account_move_line_id AS line_id,
                    string_agg(
                        CASE
                            WHEN pg_typeof(tax.name)::text = 'jsonb' THEN
                                COALESCE( (tax.name::jsonb)->>'es_EC', (tax.name::jsonb)->>'en_US', tax.name::text )
                            ELSE tax.name::text
                        END,
                        ', '
                    ) AS names
                FROM account_move_line_account_tax_rel rel
                JOIN account_tax tax ON tax.id = rel.account_tax_id
                GROUP BY rel.account_move_line_id
            ) AS taxes ON taxes.line_id = aml.id

            WHERE
                COALESCE(aml.display_type, 'product') NOT IN ('line_note','payment_term','tax','line_section')
                AND am.state = 'posted'
                AND j.type = 'purchase'
        """

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"CREATE OR REPLACE VIEW {self._table} AS ({self._table_query})")