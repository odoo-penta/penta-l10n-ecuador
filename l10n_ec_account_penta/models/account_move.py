# -*- coding: utf-8 -*-
from odoo import models,fields, _
from odoo.exceptions import UserError
from datetime import datetime


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    def action_post(self):
        for record in self:
            # Validamos el control de asientos
            if record.journal_id and record.journal_id.entry_control == 'current_month':
                now = fields.Datetime.context_timestamp(record, datetime.now())
                # Validamos que la fecha del asiento esté en el mismo mes y año
                if record.date.month != now.month or record.date.year != now.year:
                    raise UserError(_("This journal only allows entries within the current month."))
        return super().action_post()

    def penta_cb_action_conciliation(self):
        """ This function is called by the 'Reconcile' button of account.move.line's
        list view. It performs reconciliation between the selected lines.
        - If the reconciliation can be done directly we do it silently
        - Else, if a write-off is required we open the wizard to let the client enter required information
        """
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError(_("No lines to reconcile."))
    
        reconcile_lines = self.line_ids.filtered(lambda line: line.account_id.reconcile 
                                                 or line.account_id.account_type == 'liability_payayble')
        
        if not reconcile_lines:
            raise UserError(_("It's account move not has account move lines."))
        
        
        return {
            'name': _('Reconcile'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.reconcile.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('account_accountant.view_account_reconcile_wizard').id,
            'target': 'new',
            'context': {
                'active_model': 'account.move.line',
                'active_ids': reconcile_lines.ids,
                'post_reconcile_move_id': self.id,
            },
        }