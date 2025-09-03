# -*- coding: utf-8 -*-
{
    'name': 'Penta Bank Days',
    'version': '1.0',
    'category': 'Accounting',
    'author': 'Pentalab',
    'website': 'https://pentalab.tech/',
    'license': 'LGPL-3',
    'depends': ['account', 'point_of_sale','l10n_ec_reports_penta'],
    'data': [
        'security/ir.model.access.csv',
        'views/penta_bank_days_views.xml',
        'views/penta_bank_days_menu.xml',
        'views/account_payment_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
