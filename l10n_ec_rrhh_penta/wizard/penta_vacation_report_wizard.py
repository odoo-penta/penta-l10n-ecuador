# -*- coding: utf-8 -*-
import io
import base64
from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    import xlsxwriter
except Exception:
    xlsxwriter = None


class PentaVacationReportWizard(models.TransientModel):
    _name = "penta.vacation.report.wizard"
    _description = "Reporte de Vacaciones (wizard)"

    company_id = fields.Many2one(
        "res.company", string="Compañía", default=lambda s: s.env.company
    )
    employee_ids = fields.Many2many("hr.employee", string="Empleados")
    department_id = fields.Many2one("hr.department", string="Departamento")
    include_zero = fields.Boolean(string="Incluir sin movimientos", default=False)

    # líneas en pantalla
    line_ids = fields.One2many("penta.vacation.report.line", "wizard_id", string="Líneas")

    # archivo de salida
    xlsx_file = fields.Binary(string="Archivo", readonly=True)
    xlsx_filename = fields.Char(string="Nombre de archivo", readonly=True)

    # ---------- helpers ----------
    def _domain_employees(self):
        domain = []
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        if self.department_id:
            domain.append(("department_id", "=", self.department_id.id))
        if self.employee_ids:
            domain.append(("id", "in", self.employee_ids.ids))
        return domain

    # ---------- generación ----------
    def _build_lines(self):
        self.ensure_one()

        Employee = self.env["hr.employee"].sudo()
        emps = Employee.search(self._domain_employees(), order="name")

        vals_list = []
        for emp in emps:
            entitled = emp.vac_total_entitled or 0.0
            taken = emp.vac_total_taken or 0.0
            available = emp.vac_total_available or 0.0

            if not self.include_zero and (not entitled and not taken and not available):
                continue

            vals_list.append({
                "wizard_id": self.id,
                "employee_id": emp.id,
                "employee_name": emp.name or "",
                "identification": emp.identification_id or "",
                "company_name": emp.company_id.display_name if emp.company_id else "",
                "department_name": emp.department_id.display_name if emp.department_id else "",
                "job_name": emp.job_id.display_name if emp.job_id else "",
                "allocated": entitled,
                "taken": taken,
                "balance": available,
                "leave_type_name": _("Vacaciones"),
            })

        self.line_ids.unlink()
        if vals_list:
            self.env["penta.vacation.report.line"].create(vals_list)

    # ---------- acciones ----------
    def action_generate(self):
        self._build_lines()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "name": _("Reporte de Vacaciones"),
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_export_xlsx(self):
        """Exporta a Excel"""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("No hay líneas para exportar. Primero genera el reporte."))

        if not xlsxwriter:
            raise UserError(_("No se encontró la librería 'xlsxwriter'."))

        bio = io.BytesIO()
        wb = xlsxwriter.Workbook(bio, {"in_memory": True})
        ws = wb.add_worksheet("Vacaciones")

        fmt_title = wb.add_format({"bold": True, "font_size": 14})
        fmt_hdr = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
        fmt_txt = wb.add_format({"border": 1})
        fmt_num = wb.add_format({"border": 1, "num_format": "#,##0.00"})

        title = _("Reporte de Vacaciones (desde hr.employee)")
        ws.merge_range(0, 0, 0, 8, title, fmt_title)

        headers = [
            "Empleado", "Identificación", "Compañía", "Departamento", "Puesto",
            "Tipo de ausencia", "Acreditadas", "Tomadas", "Disponibles",
        ]
        ws.write_row(2, 0, headers, fmt_hdr)

        r = 3
        for line in self.line_ids:
            ws.write(r, 0, line.employee_name or "", fmt_txt)
            ws.write(r, 1, line.identification or "", fmt_txt)
            ws.write(r, 2, line.company_name or "", fmt_txt)
            ws.write(r, 3, line.department_name or "", fmt_txt)
            ws.write(r, 4, line.job_name or "", fmt_txt)
            ws.write(r, 5, line.leave_type_name or "", fmt_txt)
            ws.write_number(r, 6, line.allocated or 0.0, fmt_num)
            ws.write_number(r, 7, line.taken or 0.0, fmt_num)
            ws.write_number(r, 8, line.balance or 0.0, fmt_num)
            r += 1

        ws.set_column("A:A", 28)
        ws.set_column("B:B", 18)
        ws.set_column("C:E", 22)
        ws.set_column("F:I", 18)

        wb.close()
        data = base64.b64encode(bio.getvalue())
        fname = "reporte_vacaciones_empleados.xlsx"

        self.write({"xlsx_file": data, "xlsx_filename": fname})

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "name": _("Reporte de Vacaciones"),
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
