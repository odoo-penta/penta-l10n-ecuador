# -*- coding: utf-8 -*-
{
    'name': "stock_report_abc.",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Inventory/Inventory',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','product', 'stock', 'sale'],

    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/abc_classification_config.xml",
        "views/product_sold_views.xml",
        "views/product_views.xml",
        "views/product_abc_history_views.xml",
        "data/cron.xml",
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
}

