# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.tools.misc import formatLang

class AccountFollowupReport(models.AbstractModel):
    _inherit = 'account.followup.report'

    # Fila “inline” con el mismo layout de los totales (3 vacías + etiqueta + importe)
    def _make_inline_total_row(self, label, amount_str):
        # El template original usa 5 columnas (3 vacías y 2 con texto/importe)
        empty = {'name': '', 'template': 'account_followup.line_template'}
        strong = {
            'name': label,
            'style': 'text-align:right; white-space:normal; font-weight: 600;',
            'template': 'account_followup.line_template',
        }
        value = {
            'name': amount_str,
            'style': 'text-align:right; white-space:normal; font-weight: 600;',
            'template': 'account_followup.line_template',
        }
        return {
            'id': f'inline-{label}',
            'name': '',
            'class': 'total',                # mismo estilo que los totales
            'style': '',                     # sin borde doble
            'unfoldable': False,
            'level': 3,
            'columns': [empty, empty, empty, strong, value],
        }

    def _get_followup_report_lines(self, options):
        # 1) líneas originales
        lines = super()._get_followup_report_lines(options)

        # 2) Totales desde tu helper (ya con los filtros del Partner Ledger)
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        totals = partner._get_followup_totals(options)

        # 3) Formateo de números (usa moneda de la compañía; si manejas multi-moneda,
        #    aquí podrías mejorar para detectar la moneda por bloque).
        currency = self.env.company.currency_id
        overdue_str = formatLang(self.env, totals.get('total_overdue', 0.0), currency_obj=currency)
        due_str     = formatLang(self.env, totals.get('total_due', 0.0),     currency_obj=currency)

        # 4) Recorremos y vamos agregando las filas “inline” cuando toca
        new_lines = []
        for line in lines:
            new_lines.append(line)

            if line.get('class') == 'total':
                cols = line.get('columns') or []
                label = ''
                if len(cols) >= 2:
                    label = (cols[-2].get('name') or '').strip()

                # Debajo del “Total Overdue” agregamos “Vencido”
                if label in ('Total Overdue', _('Total Overdue'), 'Total vencido', 'Total Vencido'):
                    new_lines.append(self._make_inline_total_row(_('Vencido'), overdue_str))

                # Debajo del “Total Due” lo renombramos a “Total Corriente”
                # y agregamos la fila “Corriente”
                if label in ('Total Due', _('Total Due')):
                    # renombrar el header del total a "Total Corriente"
                    cols[-2]['name'] = _('Total Corriente')
                    new_lines.append(self._make_inline_total_row(_('Corriente'), due_str))

        return new_lines