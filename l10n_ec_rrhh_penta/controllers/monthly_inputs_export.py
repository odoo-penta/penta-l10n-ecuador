# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request, content_disposition
import io
from odoo.tools.misc import xlsxwriter
from datetime import datetime

def _collect_structs_and_types(run):
    # estructuras presentes en los slips del lote
    structs = run.slip_ids.mapped("struct_id")
    if not structs:
        # fallback: si el lote tiene struct_id (según versión)
        if getattr(run, "struct_id", False):
            structs = run.struct_id
    # tipos de entrada de esas estructuras
    input_types = request.env["hr.payslip.input.type"].search([("struct_id", "in", structs.ids)])
    # si no encuentran struct_id en tipos, exporta todos como plan B
    if not input_types:
        input_types = request.env["hr.payslip.input.type"].search([])
    # Ordenar por code, luego por name
    input_types = input_types.sorted(lambda t: (t.code or "", t.name or ""))
    return input_types

def _days_worked_of_slip(slip):
    # suma de días trabajados no licencia
    worked_lines = slip.worked_days_line_ids
    # preferimos línea WORK100 si existe
    pref = worked_lines.filtered(lambda l: (l.work_entry_type_id.code or "").upper() == "WORK100")
    if pref:
        return pref[0].number_of_days or 0.0
    # si no, suma las líneas que no son licencia (heurística)
    non_leave = worked_lines.filtered(lambda l: not l.work_entry_type_id.is_leave)
    if non_leave:
        return sum(non_leave.mapped("number_of_days"))
    return sum(worked_lines.mapped("number_of_days"))

class MonthlyInputsExport(http.Controller):

    @http.route(
        ["/pentalab/payslip_run/<int:run_id>/export_monthly_inputs_xlsx"],
        type="http", auth="user"
    )
    def export_monthly_inputs_xlsx(self, run_id, **kw):
        env = request.env
        run = env["hr.payslip.run"].browse(run_id)
        if not run.exists():
            return request.not_found()

        input_types = _collect_structs_and_types(run)

        # --------- Construir XLSX ----------
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})
        ws = wb.add_worksheet("Novedades")

        fmt_hdr = wb.add_format({"bold": True, "bg_color": "#E6E6E6", "border": 1})
        fmt_txt = wb.add_format({"border": 1})
        fmt_num = wb.add_format({"border": 1, "num_format": "#,##0.00"})

        # columnas fijas
        headers = [
            _("Cédula"),
            _("Empleado"),
            _("Departamento"),
            _("Cargo"),
            _("Días trabajados"),
        ]
        # columnas dinámicas por input.type
        dynamic_cols = []
        for t in input_types:
            label = f"{(t.code or '').strip()} - {(t.name or '').strip()}".strip(" -")
            dynamic_cols.append((t.id, label))

        # escribir encabezados
        for i, h in enumerate(headers):
            ws.write(0, i, h, fmt_hdr)
        base_cols = len(headers)
        for j, (_, label) in enumerate(dynamic_cols):
            ws.write(0, base_cols + j, label, fmt_hdr)

        # anchos
        ws.set_column(0, 0, 16)    # cédula
        ws.set_column(1, 1, 30)    # empleado
        ws.set_column(2, 3, 22)    # dpto / cargo
        ws.set_column(4, 4, 16)    # días
        ws.set_column(base_cols, base_cols + len(dynamic_cols) - 1, 18)

        # filas por empleado (slip del lote)
        row = 1
        for slip in run.slip_ids.sorted(lambda s: (s.employee_id.name or "")):
            emp = slip.employee_id
            ws.write(row, 0, emp.identification_id or "", fmt_txt)
            ws.write(row, 1, emp.name or "", fmt_txt)
            ws.write(row, 2, emp.department_id.name or "", fmt_txt)
            ws.write(row, 3, emp.job_id.name or "", fmt_txt)
            ws.write_number(row, 4, _days_worked_of_slip(slip), fmt_num)

            # valores actuales de inputs por tipo → dict {type_id: amount}
            current_map = {}
            for inp in slip.input_line_ids:
                if inp.input_type_id:
                    current_map[inp.input_type_id.id] = float(inp.amount or 0.0)

            # escribe cada columna dinámica
            for j, (type_id, _) in enumerate(dynamic_cols):
                ws.write_number(row, base_cols + j, float(current_map.get(type_id, 0.0)), fmt_num)
            row += 1

        wb.close()
        data = output.getvalue()
        output.close()

        filename = f"novedades_{(run.name or 'lote')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(filename)),
        ]
        return request.make_response(data, headers)
