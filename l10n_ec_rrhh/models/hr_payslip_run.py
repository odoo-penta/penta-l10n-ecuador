# -*- coding: utf-8 -*-
from odoo import api, fields, models

class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    penta_benefit_key = fields.Selection([
        ("13th", "Décimo Tercer"),
        ("14_costa", "Décimo Cuarto Costa"),
        ("14_sierra", "Décimo Cuarto Sierra"),
        ("utilities", "Utilidades"),
    ], help="Se establece vía contexto desde los menús de Beneficios.")

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        key = self.env.context.get("penta_benefit_key")
        if key:
            cfg = self.env["penta.benefit.config"]
            d_start, d_end = cfg.compute_period_for_year(key, ref_date=fields.Date.today())
            if d_start and d_end:
                # Solo si los campos están en la vista/creación
                if "date_start" in fields_list:
                    vals["date_start"] = d_start
                if "date_end" in fields_list:
                    vals["date_end"] = d_end
                vals["penta_benefit_key"] = key
        return vals
