# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

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
                if "date_start" in fields_list:
                    vals["date_start"] = d_start
                if "date_end" in fields_list:
                    vals["date_end"] = d_end
                vals["penta_benefit_key"] = key
        return vals
    
    def action_export_payroll_xlsx(self):
        self.ensure_one()
        if not self.slip_ids:
            raise UserError(_("No hay nóminas (hr.payslip) en este lote para exportar."))

        # Abrimos en nueva pestaña para descargar
        url = f"/pentalab/payroll_run/{self.id}/export_xlsx"
        return {
            "type": "ir.actions.act_url",
            "name": _("Generar reporte de nómina"),
            "url": url,
            "target": "self",
        }
        
    def action_export_monthly_inputs_xlsx(self):
        self.ensure_one()
        if not self.slip_ids:
            raise UserError(_("No hay recibos en este lote."))
        # descarga directa vía controlador
        return {
            "type": "ir.actions.act_url",
            "name": _("Exportar novedades mensuales"),
            "url": f"/pentalab/payslip_run/{self.id}/export_monthly_inputs_xlsx",
            "target": "self",
        }

    def action_open_import_monthly_inputs_wizard(self):
        self.ensure_one()
        if not self.slip_ids:
            raise UserError(_("No hay recibos en este lote."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "pentalab.import.monthly.inputs.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_run_id": self.id},
        }
        
    def _create_account_move(self, values):
        employee_partner = self.employee_id.address_home_id

        if employee_partner and values.get('line_ids'):
            new_lines = []
            for command in values['line_ids']:
                if command[0] == 0 and isinstance(command[2], dict):
                    line_vals = command[2]

                    # Asignar el partner SOLO si no viene ya definido
                    line_vals.setdefault('partner_id', employee_partner.id)

                    new_lines.append((0, 0, line_vals))
                else:
                    new_lines.append(command)

            values['line_ids'] = new_lines

        return super()._create_account_move(values)
