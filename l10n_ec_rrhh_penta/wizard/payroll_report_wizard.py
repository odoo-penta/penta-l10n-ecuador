# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError

class popupwizard(models.TransientModel):
    _name = 'popup.wizard'
    _description = 'Popup Wizard'

    lote = fields.Many2one('hr.payslip.run')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        help='Company',
        default=lambda self: self.env.company,
        exportable=True,
        store=True,
    )
    date_from = fields.Date()
    date_to = fields.Date()
    
    @api.onchange('lote')
    def _onchange_lote(self):
        if self.lote:
            self.date_from = False
            self.date_to = False
            
    @api.onchange('date_from', 'date_to')
    def _onchange_dates(self):
        if self.date_from or self.date_to:
            self.lote = False

    def action_confirm(self):
        for wizard in self:
            if not self.lote and not (self.date_from and self.date_to):
                raise UserError(
                    'Debe seleccionar un Lote o un rango de Fechas.'
                )
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise UserError('La Fecha Inicio debe ser menor o igual que la Fecha Fin.')
        action = self.env.ref('l10n_ec_rrhh_penta.report_payroll_xlsx').report_action(self)
        return action
