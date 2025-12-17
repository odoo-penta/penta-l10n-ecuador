from odoo import models, fields, _


class L10nLatamDocumentType(models.Model):
    _inherit = 'l10n_latam.document.type'

    penta_cb_length_auth_number = fields.Integer(
        string=_("Lenght of Authorization Number"),
        help=_("Length of the authorization number for this document type. "
               "If specified, the authorization number will be validated for length when creating or editing documents.")
    )
    
    penta_cb_move_type = fields.Many2many(
        comodel_name='penta.cb.move.type',
        relation='l10n_latam_document_type_penta_cb_move_type_rel',
        column1='document_type_id',
        column2='move_type_id',
        string=_("Allowed Move Types"),
        help=_("Select the move types that are allowed for authorization number validation.")
    )
    