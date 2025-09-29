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
    "name": "POS",
    'summary': 'POS in backend',
    "version": "18.0.1.0",
    'description': """
        Adds a new POS sales menu that processes everything in real time on the backend
    """,
    'author': 'PentaLab',
    'maintainer': 'PentaLab',
    'contributors': ['AntonyPineda <vini16.av@gmail.com>'],
    'website': 'https://pentalab.tech/',
    'license': 'OPL-1',
    'category': 'Sales/Sales',
    'depends': [
        'sale_stock',
        'l10n_ec_account_penta',
    ],
    'data': [
        'data/ir_sequence.xml',
        'data/cash_reports.xml',
        'data/coins.xml',
        
        'security/cash_box_groups.xml',
        'security/cash_box_rules.xml',
        'security/ir.model.access.csv',
        
        'report/report_cash_closing.xml',
        'report/reports.xml',
        
        'wizard/cash_box_wizard_view.xml',
        'wizard/res_config_settings_views.xml',
        
        'views/cash_box_views.xml',
        'views/coin_views.xml',
        'views/sale_order_views.xml',
        'views/cash_menuitems.xml',
    ],
    'installable': True,
    'application': True,
}
