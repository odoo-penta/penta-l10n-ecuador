# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

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
    
    def action_publish_payslips(self):
        for payslip_run in self:
            for slip in payslip_run.slip_ids:
                if slip.move_id.state != 'posted':
                    if not slip.move_id:
                        raise UserError(_("Existen recibos de nómina sin asiento contable generado. Por favor, genere los asientos antes de publicar los recibos: %s") % slip.name)
                    if not slip.move_id.line_ids:
                        raise UserError(_("El asiento contable del recibo de nómina %s no tiene líneas contables.") % slip.name)
                    slip.move_id.action_post()
    
    def action_export_payroll_xlsx(self):
        self.ensure_one()
        if not self.slip_ids:
            raise UserError(_("No hay nóminas (hr.payslip) en este lote para exportar."))
        wizard = self.env['popup.wizard'].create({
            'lote': self.id,
            'company_id': self.env.user.company_id.id
        })
        return wizard.action_confirm()
    
    def action_export_thirteenth_xlsx(self):
        self.ensure_one()
        if not self.slip_ids:
            raise UserError(_("No hay nóminas (hr.payslip) en este lote para exportar."))
        action = self.env.ref('l10n_ec_rrhh_penta.report_thirteenth_xlsx').report_action(self)
        return action
        
    def action_export_monthly_inputs_xlsx(self):
        self.ensure_one()
        if not self.slip_ids:
            raise UserError(_("No hay recibos en este lote."))
        # descarga directa vía controlador
        return {
            "type": "ir.actions.act_url",
            "name": "Exportar novedades mensuales",
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
        
    def action_validate(self):
        precision = self.env['decimal.precision'].precision_get('Payroll')

        payslips = self.slip_ids
        # 1. Validación de estados
        for payslip in self.slip_ids:
            if payslip.state != 'verify':
                raise UserError("El recibo de nómina %s no está en estado 'En espera'. No se puede validar el lote." % payslip.name)
        
        # 2. Marcar recibos como hechos
        payslips.write({'state': 'done'})
        
        # 3. Validaciones contables
        if any(not slip.struct_id for slip in payslips):
            raise UserError("Existen recibos sin estructura salarial.")
        if any(not slip.struct_id.journal_id for slip in payslips):
            raise UserError("Existen estructuras sin diario contable configurado.")
        
        journal = payslips[0].struct_id.journal_id
        date = fields.Date.end_of(payslips[0].date_to, 'month')
        line_ids = []
        debit_sum = credit_sum = 0.0
        narration = ''

        # 4. Generar líneas contables de TODOS los empleados
        for slip in payslips:
            narration += f"{slip.number or ''} - {slip.employee_id.name}<br/>"

            partner = slip.employee_id._get_related_partners()
            if not partner:
                raise UserError("El empleado %s no tiene contacto asociado." % slip.employee_id.name)
            
            slip_lines = slip._prepare_slip_lines(date, [])

            for line in slip_lines:
                line['partner_id'] = partner.id
                debit_sum += line.get('debit', 0.0)
                credit_sum += line.get('credit', 0.0)
                line_ids.append(line)
        
        # 5. Ajuste por descuadre
        if float_compare(debit_sum, credit_sum, precision_digits=precision) == 1:
            payslips[0]._prepare_adjust_line(
                line_ids, 'credit', debit_sum, credit_sum, date
            )
        elif float_compare(credit_sum, debit_sum, precision_digits=precision) == 1:
            payslips[0]._prepare_adjust_line(
                line_ids, 'debit', debit_sum, credit_sum, date
            )

        # 6. Crear asiento contable
        move_vals = {
            'journal_id': journal.id,
            'date': date,
            'ref': date.strftime('%B %Y'),
            'narration': narration,
            'line_ids': [(0, 0, line) for line in line_ids],
        }

        move = self.env['account.move'].create(move_vals)
        
        # 7. Enlazar asiento
        payslips.write({
            'move_id': move.id,
            'date': date,
        })
        self.write({'move_id': move.id})

        # 8. Cerrar lote
        self.action_close()
    
    """
    def action_draft(self):
        import pdb;pdb.set_trace()
        if self.move_id:
            self.move_id.button_draft(self)
        return super().action_draft(self)
    """