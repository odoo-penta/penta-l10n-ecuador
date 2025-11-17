from odoo import models, fields, api, _


class PentaCBMoveType(models.Model):
    _name = 'penta.cb.move.type'
    _description = 'Allowed Move Type'
    
    
    code = fields.Selection([
        ('in_invoice', _('Vendor Bill')),
        ('in_refund', _('Vendor Refund')),
        ('out_invoice', _('Customer Invoice')),
        ('out_refund', _('Customer Refund')),
        ('entry', _('Journal Entry')),
    ], string='Move Type', required=True, help='Technical move_type used in account.move')
    
    name = fields.Char(string="Name", compute='_compute_name', 
                       store=True, help='The name of the move type.',
                       translate=True)
    
    _sql_constraints = [
        ('penta_move_type_unique', 'UNIQUE(code)', 'Move type must be unique.'),
    ]
    
    @api.depends('code')
    def _compute_name(self):
        for record in self:
            record.name = dict(self._fields['code'].selection).get(record.code, '')
            
    # Este método asegura que el Many2many muestre un texto traducible
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, rec.name))
        return result