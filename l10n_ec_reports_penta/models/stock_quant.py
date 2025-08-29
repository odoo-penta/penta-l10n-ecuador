from odoo import models, fields, api

PRODUCT_CATEGORY_MODEL = 'product.category'

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    store_location = fields.Char(related='location_id.name', string="Ubicación", translate=False)
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén',
        related='location_id.warehouse_id'
    )
    packaging_name = fields.Char(related='product_id.packaging_name', string="Embalaje")
    main_category_id = fields.Many2one(
        PRODUCT_CATEGORY_MODEL,
        string='Categoría principal',
        related='product_id.categ_id'
    )
    category_id = fields.Many2one(
        PRODUCT_CATEGORY_MODEL,
        string='Categoría',
        related='product_id.categ_id.parent_id'
    )
    subcategory_id = fields.Many2one(
        PRODUCT_CATEGORY_MODEL,
        string='Subcategoría',
        related='product_id.categ_id.parent_id.parent_id'
    )
    quantity = fields.Float(string="Cantidad a la mano", readonly=True)
    default_code = fields.Char(related='product_id.default_code', string="Código del producto", translate=False)
    product_name = fields.Char(related='product_id.name', string="Nombre del producto", translate=False)
    attributes_and_variants = fields.Char(
        string="Atributos y variantes",
        compute='_compute_attributes_and_variants',
        help="Atributos y variantes del producto, como calidad, matiz, calibre, etc."
    )
    
    @api.depends('product_id.attribute_line_ids')
    def _compute_attributes_and_variants(self):
        for rec in self:
            attributes = []
            for line in rec.product_id.attribute_line_ids:
                for value in line.value_ids:
                    attributes.append(f"{line.attribute_id.name}: {value.name}")
            rec.attributes_and_variants = ', '.join(attributes) if attributes else 'N/A'

    