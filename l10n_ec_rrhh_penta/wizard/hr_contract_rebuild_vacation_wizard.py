# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class HrContractRebuildVacationWizard(models.TransientModel):
    _name = "hr.contract.rebuild.vacation.wizard"
    _description = "Confirmar Recalculo de Vacaciones"

    contract_ids = fields.Many2many("hr.contract", string="Contratos", required=True)

    def action_confirm(self):
        """Ejecuta el recalculo real"""
        self.contract_ids.action_confirm_rebuild_vacation_balances()
        return {"type": "ir.actions.act_window_close"}
