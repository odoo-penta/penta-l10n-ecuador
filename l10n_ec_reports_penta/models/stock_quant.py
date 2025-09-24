from odoo import models, fields, api

PRODUCT_CATEGORY_MODEL = 'product.category'

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    store_location = fields.Char(related='location_id.name', string="Ubicación", translate=False)
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Nombre Almacén',
        related='location_id.warehouse_id'
    )
    packaging_name = fields.Char(related='product_id.packaging_name', string="Embalaje")
    main_category_id = fields.Many2one(
        PRODUCT_CATEGORY_MODEL,
        string='Categoría',
        related='product_id.categ_id',
        store=True, index= True
    )
    # Niveles desde la RAÍZ (si no existe, queda False, manteniendo la alineación)
    cat_l1_id = fields.Many2one('product.category', string='Nivel 1 (raíz)',
                                compute='_compute_category_levels', store=True, index=True)
    cat_l2_id = fields.Many2one('product.category', string='Nivel 2',
                                compute='_compute_category_levels', store=True, index=True)
    cat_l3_id = fields.Many2one('product.category', string='Nivel 3',
                                compute='_compute_category_levels', store=True, index=True)
    cat_l4_id = fields.Many2one('product.category', string='Nivel 4',
                                compute='_compute_category_levels', store=True, index=True)
    cat_l5_id = fields.Many2one('product.category', string='Nivel 5',
                                compute='_compute_category_levels', store=True, index=True)
    cat_l6_id = fields.Many2one('product.category', string='Nivel 6',
                                compute='_compute_category_levels', store=True, index=True)
    
    
    cat_l1_name = fields.Char(related='cat_l1_id.name', string='Nombre Nivel 1', store=True)
    cat_l2_name = fields.Char(related='cat_l2_id.name', string='Nombre Nivel 2', store=True)
    cat_l3_name = fields.Char(related='cat_l3_id.name', string='Nombre Nivel 3', store=True)
    cat_l4_name = fields.Char(related='cat_l4_id.name', string='Nombre Nivel 4', store=True)
    cat_l5_name = fields.Char(related='cat_l5_id.name', string='Nombre Nivel 5', store=True)
    cat_l6_name = fields.Char(related='cat_l6_id.name', string='Nombre Nivel 6', store=True)

    cat_depth = fields.Integer(string='Profundidad categoría',
                               compute='_compute_category_levels', store=True)
    quantity = fields.Float(string="Cantidad a la mano", readonly=True)
    default_code = fields.Char(related='product_id.default_code', string="Código del producto", translate=False)
    product_name = fields.Char(related='product_id.name', string="Nombre del producto", translate=False)
    product_attribute_value_ids = fields.Many2many(
        'product.attribute.value',
        string='Attributes',
        compute='_compute_quant_product_attributes',
        store=True  # Must be stored to be filterable
    )

    @api.depends('product_id.product_template_attribute_value_ids.product_attribute_value_id')
    def _compute_quant_product_attributes(self):
        for quant in self:
            if quant.product_id:
                value_ids = quant.product_id.product_template_attribute_value_ids.product_attribute_value_id
                quant.product_attribute_value_ids = value_ids
            else:
                quant.product_attribute_value_ids = False
                
    @api.depends('product_id.categ_id', 'product_id.categ_id.parent_path')
    def _compute_category_levels(self):
        category = self.env['product.category']
        for rec in self:
            cat = rec.product_id.categ_id if rec.product_id and rec.product_id.categ_id else False
            if not cat:
                rec.update({
                    'cat_l1_id': False, 'cat_l2_id': False, 'cat_l3_id': False,
                    'cat_l4_id': False, 'cat_l5_id': False, 'cat_l6_id': False, 
                    'cat_depth': 0
                })
                continue

            # parent_path es como "1/23/45/" => ids desde raíz a hoja
            ids = [int(x) for x in cat.parent_path.split('/') if x]
            chain = category.browse(ids)  # ya viene ordenada raíz->hoja

            vals = {'cat_depth': len(chain)}
            # Rellenar niveles 1..MAX_LEVELS
            levels = ['cat_l1_id', 'cat_l2_id', 'cat_l3_id', 'cat_l4_id', 'cat_l5_id', 'cat_l6_id']
            for i, fname in enumerate(levels):
                vals[fname] = chain[i] if i < len(chain) else False

            rec.update(vals)

    