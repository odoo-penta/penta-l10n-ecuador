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
    'name': "Pentalab Custom Account",
    'summary': "Pentalab Custom Account module for Ecuador",
    'description': """
    This module extends the account payment functionalities to include additional fields and features specific to Ecuadorian accounting practices.
    """,
    'author': "PentaLab",
    'contributors': [
        'Bernardo Bustamante <bbustamante@pentalab.tech>',
        'AntonyPineda <vini16.av@gmail.com>'
    ],
    'website': "https://pentalab.tech/",
    'category': 'Accounting',
    'version': '18.0.0.2',
    'depends': [
        'account_accountant',
        'account_asset',
        'sale',
        'mail',
        'account_reports',
        'product_brand',
        'loyalty',
        'penta_base'
    ],
    'data': [
        'data/account_cards_data.xml',
        'data/assets_report_extend.xml',
        'data/penta_cb_move_type_data.xml',

        'security/ir.model.access.csv',
        
        'report/account_asset_acta_report.xml',
        
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/account_cards_view.xml',
        'views/account_journal_views.xml',
        'views/account_asset_views.xml',
        'views/account_asset_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/product_views.xml',
        'views/account_payment_term_views.xml',
        'views/l10n_latam_document_type_views.xml',
        'views/loyalty_reward_views.xml',
        'views/sale_order_views.xml',
    ],
    'license': 'OPL-1',
}

