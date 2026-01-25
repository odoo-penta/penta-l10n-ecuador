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
    'name': "Pentalab Custom Account Extended",
    'summary': "Pentalab Custom Account Extended module for Ecuador",
    'description': """
    This module extends the account payment functionalities to include additional fields and features specific to Ecuadorian accounting practices.
    """,
    'author': "PentaLab",
    'contributors': [
        'AntonyPineda <vini16.av@gmail.com>'
    ],
    'website': "https://pentalab.tech/",
    'category': 'Accounting',
    'version': '18.0.2.1.1',
    'depends': [
        'l10n_ec_account_penta',
    ],
    'data': [
        'views/account_move_views.xml',
    ],
    'license': 'OPL-1',
}

