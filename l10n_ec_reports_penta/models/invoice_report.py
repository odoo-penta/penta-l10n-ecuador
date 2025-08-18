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
    purchase_order_name = fields.Char("N° pedido", readonly=True)
    auth_number = fields.Char("N° autorización", readonly=True)
    partner_vat = fields.Char("Identificación", readonly=True)
    partner_name = fields.Char("Contacto", readonly=True)
    payterm_name = fields.Char("Términos de pago", readonly=True)
    paymethod_name = fields.Char("Método de pago", readonly=True)

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
        # OJO: Forzamos SOLO asientos publicados y SOLO diarios de tipo 'purchase'
        return """
            SELECT
                aml.id AS id,

                -- IDs para filtrar
                rc.id   AS company_id,
                j.id    AS journal_id,
                rp.id   AS partner_id,

                -- Cabecera
                rc.name AS company_name,
                am.invoice_date AS invoice_date,
                am.date AS date,
                am.name AS move_name,
                j.name AS journal_name,
                ldt.name AS doc_type_name,
                am.ref AS ref,
                COALESCE(pol_po.po_names, am.invoice_origin) AS purchase_order_name,
                am.l10n_ec_authorization_number AS auth_number,
                rp.vat AS partner_vat,
                rp.name AS partner_name,
                apt.name AS payterm_name,
                paym.paymethod_names AS paymethod_name,

                -- Línea
                pp.default_code AS default_code,
                ptmpl.name AS product_name,
                pc_parent.name AS parent_categ_name,
                pc.name AS categ_name,
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

            -- Producto y categorías
            LEFT JOIN product_product pp        ON pp.id = aml.product_id
            LEFT JOIN product_template ptmpl    ON ptmpl.id = pp.product_tmpl_id
            LEFT JOIN product_category pc       ON pc.id = ptmpl.categ_id
            LEFT JOIN product_category pc_parent ON pc_parent.id = pc.parent_id

            -- Nombres de PO desde la línea de compra vinculada
            LEFT JOIN (
                SELECT pol.id AS line_id, string_agg(DISTINCT po2.name, ', ') AS po_names
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
                               ELSE
                                   tax.name::text
                           END,
                           ', '
                       ) AS names
                FROM account_move_line_account_tax_rel rel
                JOIN account_tax tax ON tax.id = rel.account_tax_id
                GROUP BY rel.account_move_line_id
            ) AS taxes ON taxes.line_id = aml.id

            -- Métodos de pago usados (simple: nombre del diario del pago)
            LEFT JOIN (
                SELECT inv.id AS inv_id,
                       string_agg(DISTINCT aj.name::text, ', ') AS paymethod_names
                FROM account_move inv
                LEFT JOIN account_move_line invaml
                  ON invaml.move_id = inv.id AND invaml.display_type IS NULL
                LEFT JOIN account_partial_reconcile apr
                  ON apr.debit_move_id = invaml.id OR apr.credit_move_id = invaml.id
                LEFT JOIN account_move_line payaml
                  ON payaml.id = CASE
                      WHEN apr.debit_move_id = invaml.id THEN apr.credit_move_id
                      ELSE apr.debit_move_id
                  END
                LEFT JOIN account_move paymove ON paymove.id = payaml.move_id
                LEFT JOIN account_payment ap    ON ap.move_id = paymove.id
                LEFT JOIN account_journal aj    ON aj.id = paymove.journal_id
                WHERE ap.id IS NOT NULL
                GROUP BY inv.id
            ) AS paym ON paym.inv_id = am.id

            WHERE
                aml.display_type IS NULL
                AND am.state = 'posted'          -- Solo publicados
                AND j.type = 'purchase'          -- Solo diarios de Compras
        """

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"CREATE OR REPLACE VIEW {self._table} AS ({self._table_query})")