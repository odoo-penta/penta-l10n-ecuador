# -*- coding: utf-8 -*-
#################################################################################
# Author      : PentaLab (<https://pentalab.tech>)
# Copyright(c): 2025
# All Rights Reserved.
#
# This module is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################
{
    'name': "Pentalab Custom Stock",
    'summary': "Pentalab Custom Stock module for Ecuador",
    'description': """
    This module extends the stock functionalities to include additional fields and features specific to Ecuadorian inventory practices.
    """,
    'author': "PentaLab",
    'contributors': [
        'AntonyPineda <vini16.av@gmail.com>'
    ],
    'website': "https://pentalab.tech/",
    'category': 'Inventory/Inventory',
    'version': '18.0.2.1.1',
    'depends': [
        'stock',
    ],
    'data': [
        'views/stock_picking_views.xml',
        'views/report_stockpicking_operations.xml',
    ],
    'license': 'OPL-1',
}

