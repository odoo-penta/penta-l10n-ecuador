from odoo import models, _

class AccountReconcileWizard(models.TransientModel):
    _inherit = 'account.reconcile.wizard'

    def reconcile(self):
        # Obtener los apuntes a conciliar desde el contexto
        active_ids = self.env.context.get("active_ids", [])
        result = super().reconcile()

        # Registrar log solo si hay factura relacionada
        if active_ids:
            lines = self.env['account.move.line'].browse(active_ids)
            moves = lines.mapped("move_id")  # pueden ser varias facturas

            for move in moves:
                move.message_post(
                    body=_(
                        "Se ha realizado la conciliación en los apuntes con IDs: %s"
                    ) % (", ".join(map(str, active_ids))),
                    message_type="notification",
                )
        return result
