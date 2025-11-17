# -*- coding: utf-8 -*-
from odoo import models,fields, _
from odoo.exceptions import UserError, ValidationError
import re
from datetime import datetime


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
    
    REGEX_PATTERN_DOC_TYPE = r"^\s+|\s+$" # Only leading and trailing spaces

    def _check_move_type(self):
        for record in self:
            document_type = record.l10n_latam_document_type_id
            print(document_type.penta_cb_length_auth_number)
            print(record.move_type)
            print(record.l10n_latam_document_type_id.penta_cb_move_type.mapped('code'))
            if document_type.penta_cb_length_auth_number <= 0 or \
            record.move_type not in record.l10n_latam_document_type_id.penta_cb_move_type.mapped('code'):
                print('FALSE')
                return False
        return True

    
    def write(self, vals):
        res = super(AccountMove, self).write(vals)
        
        if (('l10n_ec_authorization_number' in vals) or ('l10n_latam_document_type_id' in vals)) and \
        self.status_in_payment != 'draft' and self._check_move_type():
            self._check_authorization_length()
            self._check_authorization_unique()

        return res

    def _check_authorization_length(self):
        for move in self:
            document_type = move.l10n_latam_document_type_id
            auth_number = move.l10n_ec_authorization_number or ''
            if not document_type or not auth_number:
                raise ValidationError(
                    f"El numero de autorizacion y tipo de documento son obligatorios para el movimiento contable {move.name.strip()}."
                )
            
            if document_type.penta_cb_length_auth_number and \
                document_type.penta_cb_length_auth_number > 0  and \
                (len(auth_number) != document_type.penta_cb_length_auth_number):
                length = re.sub(r"\s+", "", str(document_type.penta_cb_length_auth_number))
                doc_name = re.sub(self.REGEX_PATTERN_DOC_TYPE, "", str(document_type.display_name))  # solo inicio/fin
                raise ValidationError(
                    f"El numero de autorizacion debe contener exactamente {length} digitos para el tipo de documento {doc_name}."
                )
                
    def _check_authorization_unique(self):
        for move in self:
            auth_number = move.l10n_ec_authorization_number or ''
            if not auth_number:
                continue

            record_account = self.env['account.move'].search([
                ('l10n_ec_authorization_number', '=', auth_number),
                ('l10n_latam_document_type_id', '=', move.l10n_latam_document_type_id.id),
                ('id', '!=', move.id)
            ])
            if record_account and len(record_account) > 0:
                auth_number = re.sub(r"\s+", "", str(record_account.l10n_ec_authorization_number))
                doc_name = re.sub(self.REGEX_PATTERN_DOC_TYPE, "", str(record_account.name))  # solo inicio/fin
                doc_type_name = re.sub(self.REGEX_PATTERN_DOC_TYPE, "", str(record_account.l10n_latam_document_type_id.display_name))  # solo inicio/fin
                raise ValidationError(
                    f"El numero de autorizacion {auth_number} ya existe en el documento {doc_name} con el tipo de documento {doc_type_name}."
                )
            
    def action_post(self):
        # 1) Validación de control de asientos por mes actual
        for record in self:
            if record.journal_id and record.journal_id.entry_control == 'current_month':
                now = fields.Datetime.context_timestamp(record, datetime.now())
                # Validamos que la fecha del asiento esté en el mismo mes y año
                if record.date.month != now.month or record.date.year != now.year:
                    raise UserError(_("This journal only allows entries within the current month."))

        # 2) Llamamos al super para que se contabilice el asiento
        res = super(AccountMove, self).action_post()

        # 3) Validaciones de tipo de documento y autorización
        if self._check_move_type():
            self._check_authorization_length()
            self._check_authorization_unique()

        return res