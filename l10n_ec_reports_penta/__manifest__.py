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
    "name": "Pentalab Reports",
    'summary': 'Pentalab accounting reports',
    "version": "18.0.0.1",
    'description': """
        Add new reports needed in the accounting section
    """,
    'author': 'PentaLab',
    'maintainer': 'PentaLab',
    'contributors': ['AntonyPineda <vini16.av@gmail.com>'],
    'website': 'https://pentalab.tech/',
    'license': 'OPL-1',
    "category": "Accounting/Accounting",
    "depends": [
        'account',
        'report_xlsx',
        ],
    "data": [
        "security/ir.model.access.csv",
        
        'report/reports.xml',
        'report/report_export_stock_quant_xlsx.xml',
        
        'wizard/generate_reports.xml',
        
        'report/account_move_inventory_report.xml',
        "views/account_move_inventory_report_action.xml",
        "views/pentalab_report_wizard_view.xml",
        "views/cobros_por_ventas_report.xml",
        'views/export_inventory_wizard_view.xml',
        "views/invoice_report_views.xml",
        "views/invoice_report_menu.xml",
        "views/pagos_por_compras_report.xml",
        "views/pentalab_stock_report_view.xml",
        "views/pentalab_inventory_report_view.xml",
        "views/pentalab_inventory_report_menu.xml",
        #"views/pentalab_menu_sri_report.xml",
        "views/report_dispatch_consolidated_view.xml",
        "views/report_dispatch_order_view.xml",
        "views/res_config_settings_views.xml",
        'views/pentalab_report_antiguedad_wizard.xml',
        'views/pentalab_report_antiguedad_menu.xml',
        'views/account_move_report_action.xml',
        'report/account_move_report.xml',
    ],
    "installable": True,
    'application': False,
    "auto_install": False,
}
