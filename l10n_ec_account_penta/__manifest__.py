# -*- coding: utf-8 -*-
{
    'name': "Pentalab Custom Account",
    'summary': "Pentalab Custom Account module for Ecuador",
    'description': """
    This module extends the account payment functionalities to include additional fields and features specific to Ecuadorian accounting practices.
    """,
    'author': "PentaLab",
    'website': "https://pentalab.tech/",
    'category': 'Accounting',
    'version': '0.1',
    'depends': ['account'],
    'data': [
        'views/account_payment_views.xml',
        'views/account_card_map_view.xml',
        'security/ir.model.access.csv',
        'data/account_cards_data.xml',
        'views/account_cards_view.xml',
        'views/account_journal_views.xml',
    ],
}

