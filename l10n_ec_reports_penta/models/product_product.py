# models/product_product.py
from odoo import models, fields

class ProductProduct(models.Model):
    _inherit = 'product.product'

    # calidad = fields.Char(string="Calidad", compute="_compute_custom_fields")
    # matiz = fields.Char(string="Matiz", compute="_compute_custom_fields")
    # calibre = fields.Char(string="Calibre", compute="_compute_custom_fields")
    packaging_name = fields.Char(string="Embalaje", compute="_compute_packaging")

    # def _compute_custom_fields(self):
    #     for rec in self:
    #         calidad = ''
    #         matiz = ''
    #         calibre = ''
    #         for attr in rec.product_template_attribute_value_ids:
    #             name_json = attr.attribute_id.name
    #             name = ''
    #             if isinstance(name_json, dict):
    #                 name = name_json.get('es_EC') or name_json.get('en_US') or ''
    #             else:
    #                 name = name_json

    #             name = name.strip().lower()

    #             if name == 'calidad':
    #                 calidad = attr.name
    #             elif name == 'matiz':
    #                 matiz = attr.name
    #             elif name == 'calibre':
    #                 calibre = attr.name

    #         rec.calidad = calidad
    #         rec.matiz = matiz
    #         rec.calibre = calibre


    def _compute_packaging(self):
        for rec in self:
            if rec.packaging_ids:
                rec.packaging_name = rec.packaging_ids[0].name
            else:
                rec.packaging_name = ''