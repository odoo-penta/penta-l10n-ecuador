# -*- coding: utf-8 -*-
{
    'name': 'Conciliación de Tarjetas de Crédito',
    'version': '1.0',
    'author': 'Penta',
    'category': 'Accounting',
    'summary': 'Módulo para conciliar tarjetas de crédito',
    'description': """
Este módulo permite la conciliación de tarjetas de crédito:
- Crea un modelo para las tarjetas de crédito (account.cards).
- Crea un modelo para la conciliación (credit.card.reconcile).
    """,
    'depends': [
        'base',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        
        'views/credit_card_reconcile_view.xml',
        'views/import_movements_wizard.xml',
        'views/account_journal_inherit_view.xml',
        'views/view_account_payment_form.xml',
        'views/menus.xml',
        'data/ir_sequence.xml',
        'views/account_tax_group_inherit.xml',
        'security/credit_card_reconcile.xml'
    ],
    'installable': True,
    'application': False,
}
