from odoo import models, _
import re

class AccountReconcileWizard(models.TransientModel):
    _inherit = 'account.reconcile.wizard'

    def reconcile(self):
        active_ids = self.env.context.get("active_ids") or []
        moves = self.env['account.move.line'].browse(active_ids).mapped("move_id")

        res = super().reconcile()

        if not active_ids:
            return res

        lines = self.env['account.move.line'].browse(active_ids)

        # Postear un mensaje por documento
        by_move = {}
        for l in lines:
            by_move.setdefault(l.move_id, self.env['account.move.line'])
            by_move[l.move_id] |= l

        for move, mlines in by_move.items():
            # 1) Preferimos los IDs PUROS de full_reconcile_id
            ids_set = {str(fr.id) for fr in mlines.mapped('full_reconcile_id') if fr}

            # 2) Si no hubo full_reconcile_id, intentamos extraer el número del matching_number
            #    (p.ej. 'account.full.reconcile,20' -> '20')
            if not ids_set:
                for s in mlines.mapped('matching_number'):
                    if s and s != 'P':
                        m = re.search(r'(\d+)$', s)
                        if m:
                            ids_set.add(m.group(1))

            if ids_set:
                body = _("Se ha realizado la conciliación N.º: %s") % ", ".join(sorted(ids_set))
            elif any(n == 'P' for n in mlines.mapped('matching_number')):
                body = _("Se registró una conciliación parcial para estos apuntes.")
            else:
                continue

            move.message_post(
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

        return res
