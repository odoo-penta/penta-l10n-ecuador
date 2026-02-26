# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class HrLeaveType(models.Model):
    _inherit = "hr.leave.type"

    is_vacation = fields.Boolean(string="Es tipo Vacaciones", default=False, help="Debe existir solo uno por compañía.")

    @api.constrains("is_vacation", "company_id")
    def _check_single_vacation_type(self):
        for rec in self:
            if rec.is_vacation:
                dom = [("is_vacation", "=", True)]
                if rec.company_id:
                    dom += [("company_id", "=", rec.company_id.id)]
                others = self.search(dom)
                if len(others) > 1:
                    raise ValidationError("Solo puede haber un tipo de ausencia marcado como Vacaciones por compañía.")
