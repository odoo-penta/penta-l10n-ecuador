# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request, content_disposition
import io
import xlsxwriter
from datetime import datetime

# === Ajustes de clasificación por nombre de categoría ===
# Si tus categorías tienen otros nombres, ajusta aquí.
CATEGORIA_INGRESO_GRAVADO = "Ingresos (Genera beneficios sociales)"
CATEGORIAS_INGRESO_NO_GRAVADO = {"Bono", "Beneficios sociales"}
CATEGORIA_EGRESO = "Deducción"
CATEGORIA_PROVISION = "Provisión"

# Detección del Sueldo Nominal (línea del payslip) por código habitual.
SUELDO_CODES = {"BASIC", "BASICO", "SUELDO", "WAGE"}

def _safe_abs(value):
    try:
        return abs(float(value or 0.0))
    except Exception:
        return 0.0

class PayrollExportController(http.Controller):

    @http.route(['/pentalab/payroll_run/<int:run_id>/export_xlsx'], type='http', auth='user')
    def export_payroll_run_xlsx(self, run_id, **kwargs):
        env = request.env
        run = env['hr.payslip.run'].browse(run_id)
        if not run.exists():
            return request.not_found()

        # Recopilación y cálculos por empleado
        rows = []
        total_ing_grav = total_ing_no_grav = total_egresos = total_prov = 0.0
        total_total_ingresos = total_neto = total_costo = 0.0

        # Pre-cargamos categorías para evitar lookups repetidos
        def clasificar_linea(line):
            cat = (line.category_id and line.category_id.name) or ""
            if cat == CATEGORIA_INGRESO_GRAVADO:
                return "ING_GRAV"
            if cat in CATEGORIAS_INGRESO_NO_GRAVADO:
                return "ING_NO_GRAV"
            if cat == CATEGORIA_EGRESO:
                return "EGRESO"
            if cat == CATEGORIA_PROVISION:
                return "PROVISION"
            return "OTRA"

        for slip in run.slip_ids:
            employee = slip.employee_id
            contract = slip.contract_id

            # Sueldo nominal
            sueldo_nominal = 0.0
            sueldo_line = slip.line_ids.filtered(lambda l: (l.code or "").upper() in SUELDO_CODES)
            if sueldo_line:
                sueldo_nominal = _safe_abs(sueldo_line[0].total)
            elif contract and contract.wage:
                sueldo_nominal = _safe_abs(contract.wage)

            ing_grav = ing_no_grav = egresos = provisiones = 0.0

            for line in slip.line_ids:
                clase = clasificar_linea(line)
                if clase == "ING_GRAV":
                    ing_grav += _safe_abs(line.total)
                elif clase == "ING_NO_GRAV":
                    ing_no_grav += _safe_abs(line.total)
                elif clase == "EGRESO":
                    egresos += _safe_abs(line.total)
                elif clase == "PROVISION":
                    provisiones += _safe_abs(line.total)

            total_ingresos = sueldo_nominal + ing_grav + ing_no_grav
            neto = total_ingresos - egresos
            costo = total_ingresos + egresos + provisiones

            rows.append({
                "identificacion": employee.identification_id or "",
                "empleado": employee.name or "",
                "departamento": employee.department_id.name or "",
                "job": employee.job_id.name or "",
                "sueldo_nominal": sueldo_nominal,
                "ing_grav": ing_grav,
                "ing_no_grav": ing_no_grav,
                "egresos": egresos,
                "provisiones": provisiones,
                "total_ingresos": total_ingresos,
                "neto": neto,
                "costo": costo,
            })

            total_ing_grav += ing_grav
            total_ing_no_grav += ing_no_grav
            total_egresos += egresos
            total_prov += provisiones
            total_total_ingresos += total_ingresos
            total_neto += neto
            total_costo += costo

        # Crear XLSX
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet("Resumen")

        # Formatos
        fmt_title = workbook.add_format({"bold": True, "font_size": 12, "align": "center", "valign": "vcenter"})
        fmt_hdr = workbook.add_format({"bold": True, "bg_color": "#E6E6E6", "border": 1})
        fmt_txt = workbook.add_format({"border": 1})
        fmt_num = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
        fmt_green = workbook.add_format({"border": 1, "bg_color": "#C6EFCE", "num_format": "#,##0.00"}) # Ingresos
        fmt_yellow = workbook.add_format({"border": 1, "bg_color": "#FFF2CC", "num_format": "#,##0.00"}) # Egresos
        fmt_blue = workbook.add_format({"border": 1, "bg_color": "#DDEBF7", "num_format": "#,##0.00"}) # Provisiones
        fmt_total = workbook.add_format({"bold": True, "bg_color": "#D9D9D9", "border": 1, "num_format": "#,##0.00"})
        fmt_total_txt = workbook.add_format({"bold": True, "bg_color": "#D9D9D9", "border": 1})

        # Anchos
        ws.set_column("A:A", 16)  # Identificación
        ws.set_column("B:B", 32)  # Empleado
        ws.set_column("C:C", 22)  # Departamento
        ws.set_column("D:D", 22)  # Cargo
        ws.set_column("E:K", 16)

        # Título
        title = _("Resumen de Nómina - {name}").format(name=run.name or "")
        ws.merge_range(0, 0, 0, 10, title, fmt_title)

        # Subtítulo
        sub = _("Empresa: {comp}   Desde: {d}   Hasta: {h}").format(
            comp=(run.company_id.name or ""),
            d=(run.date_start or "") if run.date_start else "",
            h=(run.date_end or "") if run.date_end else "",
        )
        ws.merge_range(1, 0, 1, 10, sub, fmt_txt)

        # Encabezados
        headers = [
            _("Identificación"),
            _("Empleado"),
            _("Departamento"),
            _("Cargo"),
            _("Sueldo Nominal"),
            _("Ingresos Gravados"),
            _("Ingresos No Gravados"),
            _("Egresos"),
            _("Provisiones"),
            _("Total Ingresos"),
            _("Neto"),
            _("Costo"),
        ]
        # Nota: encolumna extra "Costo" → sumatoria de total ingresos + egresos + provisiones

        # Escribimos encabezados (fila 3, índice 2)
        row = 3
        col = 0
        for i, h in enumerate(headers):
            ws.write(row, col + i, h, fmt_hdr)

        # Escribir datos
        row += 1
        start_data_row = row
        for r in rows:
            ws.write(row, 0, r["identificacion"], fmt_txt)
            ws.write(row, 1, r["empleado"], fmt_txt)
            ws.write(row, 2, r["departamento"], fmt_txt)
            ws.write(row, 3, r["job"], fmt_txt)

            ws.write_number(row, 4, r["sueldo_nominal"], fmt_green)
            ws.write_number(row, 5, r["ing_grav"], fmt_green)
            ws.write_number(row, 6, r["ing_no_grav"], fmt_green)
            ws.write_number(row, 7, r["egresos"], fmt_yellow)
            ws.write_number(row, 8, r["provisiones"], fmt_blue)
            ws.write_number(row, 9, r["total_ingresos"], fmt_green)
            ws.write_number(row, 10, r["neto"], fmt_num)
            ws.write_number(row, 11, r["costo"], fmt_num)
            row += 1
        end_data_row = row - 1

        # Totales (fila siguiente)
        ws.write(row, 0, _("TOTALES"), fmt_total_txt)
        ws.write_blank(row, 1, None, fmt_total_txt)
        ws.write_blank(row, 2, None, fmt_total_txt)
        ws.write_blank(row, 3, None, fmt_total_txt)

        # Sueldo nominal total (suma col E)
        ws.write_formula(row, 4, f"=SUM(E{start_data_row+1}:E{end_data_row+1})", fmt_total)
        # Ingresos gravados (col F)
        ws.write_formula(row, 5, f"=SUM(F{start_data_row+1}:F{end_data_row+1})", fmt_total)
        # Ingresos no gravados (col G)
        ws.write_formula(row, 6, f"=SUM(G{start_data_row+1}:G{end_data_row+1})", fmt_total)
        # Egresos (col H)
        ws.write_formula(row, 7, f"=SUM(H{start_data_row+1}:H{end_data_row+1})", fmt_total)
        # Provisiones (col I)
        ws.write_formula(row, 8, f"=SUM(I{start_data_row+1}:I{end_data_row+1})", fmt_total)
        # Total Ingresos (col J)
        ws.write_formula(row, 9, f"=SUM(J{start_data_row+1}:J{end_data_row+1})", fmt_total)
        # Neto (col K)
        ws.write_formula(row,10, f"=SUM(K{start_data_row+1}:K{end_data_row+1})", fmt_total)
        # Costo (col L)
        ws.write_formula(row,11, f"=SUM(L{start_data_row+1}:L{end_data_row+1})", fmt_total)

        # Cierra libro
        workbook.close()
        xlsx_data = output.getvalue()
        output.close()

        filename = f"nomina_{(run.name or 'lote')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(filename)),
        ]
        return request.make_response(xlsx_data, headers=headers)
