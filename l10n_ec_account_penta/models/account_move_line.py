# -*- coding: utf-8 -*-
from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            account_id = vals.get('account_id')
            if account_id:
                account = self.env['account.account'].browse(account_id)
                # Si la cuenta pertenece al grupo de Activo, Pasivo o Patrimonios
                if account.code[0] in ['1', '2', '3'] and vals.get('analytic_distribution'):
                    # Borrar la distribución analítica
                    vals.pop('analytic_distribution', None)
        return super().create(vals_list)
    
    def write(self, vals):
        if 'analytic_distribution' in vals:
            account = self.env['account.account'].browse(vals['account_id']) if vals.get('account_id') else self.account_id
            if account.code[0] in ['1', '2', '3']:
                vals.pop('analytic_distribution', None)
        return super().write(vals)