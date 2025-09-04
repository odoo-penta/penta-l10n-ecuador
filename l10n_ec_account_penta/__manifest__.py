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
        'data/account_cards_data.xml',
        
        'security/ir.model.access.csv',
        
        'views/account_payment_views.xml',
        'views/account_cards_view.xml',
        'views/account_journal_views.xml',
    ],
}

