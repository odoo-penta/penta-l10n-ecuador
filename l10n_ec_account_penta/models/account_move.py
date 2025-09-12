from odoo import models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

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