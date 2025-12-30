from odoo import api, models, _
from odoo.exceptions import UserError

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'
    
    def action_create_payments(self):
        import pdb;pdb.set_trace()
        # Validar que no se pague facturas canceladas
        for line in self.line_ids:
            if line.move_id.state == 'cancel':
                raise UserError(_("Payments cannot be registered for cancelled invoices."))
        return super().action_create_payments()
