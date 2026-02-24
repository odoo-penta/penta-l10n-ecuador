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
    "name": "PentaLab Localización MRP",
    "summary": "Adaptaciones MRP: Configuración de parámetros, Cálculo de costos.",
    "description": """
        Adaptaciones MRP: Configuración de parámetros, Cálculo de costos.
    """,
    'author': 'PentaLab',
    'maintainer': 'PentaLab',
    'contributors': ['AntonyPineda <vini16.av@gmail.com>'],
    'website': 'https://pentalab.tech/',
    "license": "LGPL-3",
    'category': 'Penta Localización Ecuador',
    "version": "18.0.0.0.0",
    "depends": [
        'mrp',
    ],
    "data": [
        "views/account_account_views.xml",
        "views/mrp_bom_views.xml",
    ],
    "installable": True,
    "application": True,
    "images": ["static/description/icon.png", "static/description/banner.svg"],
}
