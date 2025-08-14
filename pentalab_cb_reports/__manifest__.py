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
        Add new reports needed in the accounting section.
        ==============================================
    """,
    'author': 'PentaLab',
    'maintainer': 'PentaLab',
    'contributors': ['AntonyPineda <vini16.av@gmail.com>'],
    'website': 'https://pentalab.tech/',
    'license': 'OPL-1',
    "category": "Accounting/Accounting",
    "depends": [
        'base',
        'account',
        'report_xlsx'],
    "data": [
        "security/ir.model.access.csv",
        'report/reports.xml',
        'report/report_export_stock_quant_xlsx.xml',
        'views/export_inventory_wizard_view.xml',
        'wizard/generate_reports.xml',
        "views/pentalab_inventory_report_view.xml",
        "views/pentalab_stock_report_view.xml",
        "views/pentalab_inventory_report_menu.xml",
        "views/pentalab_report_wizard_view.xml",
        "views/cobros_por_ventas_report.xml",
        "views/report_dispatch_consolidated_view.xml",
        "views/report_dispatch_order_view.xml",
    ],
    "installable": True,
    'application': False,
    "auto_install": False,
}
