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
        account_by_vals = None
        if vals.get('account_id'):
            account_by_vals = self.env['account.account'].browse(vals['account_id'])
        
        for line in self:
            account = account_by_vals or line.account_id
            if (
                account 
                and account.code 
                and isinstance(account.code, str)
                and account.code[:1] in ['1', '2', '3']
                and vals.get('analytic_distribution')
            ):
                vals.pop('analytic_distribution', None)

        return super().write(vals)