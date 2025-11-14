# -*- coding: utf-8 -*-
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
    'version': '0.1',
    'depends': [
        'account_accountant',
        'account_asset',
        'mail',
        'account_reports',
        'product_brand',
    ],
    'data': [
        'data/account_cards_data.xml',
        'data/assets_report_extend.xml',
        
        'security/ir.model.access.csv',
        
        'report/account_asset_acta_report.xml',
        
        'views/account_view_move_form.xml',
        'views/account_payment_views.xml',
        'views/account_cards_view.xml',
        'views/account_journal_views.xml',
        'views/account_asset_views.xml',
        'views/account_asset_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
    ],
    'license': 'OPL-1',
}

