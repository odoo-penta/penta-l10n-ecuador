from odoo import models, fields, api

class StockQuantAggregated(models.Model):
    _name = "stock.quant.aggregated"
    _description = "Stock agrupado por producto y ubicación padre"
    _auto = False  # Es una vista SQL, no una tabla

    product_id = fields.Many2one('product.product', string="Producto", readonly=True)
    in_date = fields.Datetime(string="Fecha de ingreso", readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string="Almacén", readonly=True)
    location_parent_id = fields.Many2one('stock.location', string="Nombre corto", readonly=True)
    quantity = fields.Float(string="Cantidad", digits='Product Unit of Measure', readonly=True)
    location_usage = fields.Selection([
        ('supplier', 'Vendor'),
        ('customer', 'Customer'),
        ('internal', 'Internal'),
        ('inventory', 'Inventory'),
        ('production', 'Production'),
        ('transit', 'Transit')
    ], string="Uso de la ubicación", readonly=True)

    default_code = fields.Char(string="Referencia interna", readonly=True)
    product_name = fields.Char(string="Producto", readonly=True)
    product_category = fields.Char(string="Artículo", readonly=True)
    product_group = fields.Char(string="Grupo", readonly=True)
    product_line = fields.Char(string="Línea", readonly=True)
    standard_price = fields.Float(string="Costo", digits='Product Price', readonly=True)
    list_price = fields.Float(string="Precio", digits='Product Price', readonly=True)

    @api.model
    def init(self):
        self.env.cr.execute("""DROP VIEW IF EXISTS stock_quant_aggregated CASCADE;""")

        self.env.cr.execute("""
CREATE OR REPLACE VIEW stock_quant_aggregated AS
WITH quant_locations AS (
    SELECT
        sq.id AS quant_id,
        sq.product_id,
        sq.quantity,
        sq.in_date,  -- <=== AÑADIDO AQUÍ
        loc.warehouse_id AS warehouse_id,
        loc.id AS location_id,
        loc.parent_path,
        loc.usage AS location_usage
    FROM stock_quant sq
    JOIN stock_location loc ON sq.location_id = loc.id
),
first_level_parent AS (
    SELECT
        quant_id,
        product_id,
        quantity,
        in_date,  -- <=== AÑADIDO AQUÍ
        warehouse_id,
        location_usage,
        split_part(trim(trailing '/' FROM parent_path), '/', 2)::int AS main_parent_id
    FROM quant_locations
    WHERE split_part(trim(trailing '/' FROM parent_path), '/', 2) IS NOT NULL
)
SELECT
    row_number() OVER (ORDER BY p.id, flp.main_parent_id) AS id,
    p.id AS product_id,
    flp.location_usage AS location_usage,
    flp.in_date AS in_date,
    flp.warehouse_id AS warehouse_id,
    flp.main_parent_id AS location_parent_id,
    p.default_code,
    COALESCE(pt.name->>'es_EC', pt.name->>'en_US', '') AS product_name,
    c.name AS product_category,
    c2.name AS product_group,
    c3.name AS product_line,
    COALESCE(
    (SELECT value::float
     FROM jsonb_each_text(p.standard_price) LIMIT 1), 
    0.0
) AS standard_price,
    COALESCE(pt.list_price, 0.0)::float AS list_price,
    COALESCE(SUM(flp.quantity), 0.0) AS quantity
FROM first_level_parent flp
INNER JOIN stock_warehouse w ON w.id = flp.warehouse_id
JOIN product_product p ON p.id = flp.product_id
JOIN product_template pt ON pt.id = p.product_tmpl_id
LEFT JOIN product_category c ON c.id = pt.categ_id
LEFT JOIN product_category c2 ON c2.id = c.parent_id
LEFT JOIN product_category c3 ON c3.id = c2.parent_id
GROUP BY
    p.id, flp.main_parent_id,
    p.default_code, pt.name, flp.in_date,
    c.name, c2.name, c3.name,
    p.standard_price, pt.list_price, flp.warehouse_id, flp.location_usage;
        """)