# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import io

class PentaImportMonthlyInputsWizard(models.TransientModel):
    _name = "pentalab.import.monthly.inputs.wizard"
    _description = "Importar novedades mensuales (XLSX) en Lote"

    run_id = fields.Many2one("hr.payslip.run", required=True, ondelete="cascade")
    file = fields.Binary(string="Archivo XLSX", required=True)
    filename = fields.Char(string="Nombre de archivo")

    def _read_xlsx(self, data):
        """Devuelve (headers:list[str], rows:list[list]) leyendo XLSX."""
        try:
            import openpyxl
        except Exception:
            raise UserError(_("Falta la librería 'openpyxl' en el servidor de Odoo."))

        stream = io.BytesIO(base64.b64decode(data))
        wb = openpyxl.load_workbook(stream, data_only=True)
        ws = wb.active

        headers = []
        rows = []
        first = True
        for row in ws.iter_rows(values_only=True):
            if first:
                headers = [str(c or "").strip() for c in row]
                first = False
            else:
                rows.append([c for c in row])
        return headers, rows

    def _find_type_by_header(self, header, type_map_by_label):
        """Header como 'CODE - Name' → busca match exacto en labels exportados."""
        return type_map_by_label.get(header.strip())

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_("Cargue un archivo XLSX."))

        # Recolecta tipos (mismos que en export)
        input_types = self.env["hr.payslip.input.type"].sudo().search([
            ("struct_id", "in", self.run_id.slip_ids.mapped("struct_id").ids)
        ])
        if not input_types:
            input_types = self.env["hr.payslip.input.type"].sudo().search([])

        # Mapa etiqueta → tipo (misma convención que export)
        type_map_by_label = {}
        for t in input_types:
            label = f"{(t.code or '').strip()} - {(t.name or '').strip()}".strip(" -")
            type_map_by_label[label] = t

        headers, rows = self._read_xlsx(self.file)
        if not headers or len(headers) < 5:
            raise UserError(_("Plantilla inválida: faltan columnas fijas."))

        # Índices fijos
        try:
            idx_ced = headers.index("Cédula")
            idx_emp = headers.index("Empleado")
            idx_dpto = headers.index("Departamento")
            idx_job = headers.index("Cargo")
            idx_days = headers.index("Días trabajados")
        except ValueError:
            raise UserError(_("Encabezados fijos no encontrados. Use el archivo exportado por el sistema."))

        # columnas dinámicas
        dyn_indices = []
        for i, h in enumerate(headers):
            if i <= idx_days:
                continue
            dyn_indices.append((i, h))

        # Mapa: identificación → slip (del lote)
        slips_by_ident = {
            (s.employee_id.identification_id or "").strip(): s
            for s in self.run_id.slip_ids
        }

        def _set_days_worked(slip, new_days):
            if new_days is None:
                return
            try:
                new_days = float(new_days)
            except Exception:
                return
            # preferimos WORK100; si no existe, primera no licencia; si no, la primera
            line = slip.worked_days_line_ids.filtered(lambda l: (l.work_entry_type_id.code or "").upper() == "WORK100")[:1]
            if not line:
                line = slip.worked_days_line_ids.filtered(lambda l: not l.work_entry_type_id.is_leave)[:1]
            if not line and slip.worked_days_line_ids:
                line = slip.worked_days_line_ids[:1]
            if line:
                line.write({"number_of_days": new_days})

        # Procesar filas
        for r in rows:
            cedula = (str(r[idx_ced] or "")).strip()
            if not cedula:
                # fila vacía
                continue
            slip = slips_by_ident.get(cedula)
            if not slip:
                # ignorar empleados que no estén en el lote
                continue

            # 1) DÍAS TRABAJADOS
            _set_days_worked(slip, r[idx_days])

            # 2) Inputs por tipo
            for i, header in dyn_indices:
                val = r[i]
                if val in (None, ""):
                    amount = 0.0
                else:
                    try:
                        amount = float(val)
                    except Exception:
                        raise UserError(_("Valor no numérico en '%s' para empleado %s") % (header, slip.employee_id.name))

                # Buscar tipo por el encabezado
                t = self._find_type_by_header(header, type_map_by_label)
                if not t:
                    # si el encabezado no coincide con tipos actuales, sáltalo
                    continue

                # Buscar/crear input único por slip+tipo
                line = self.env["hr.payslip.input"].search([
                    ("payslip_id", "=", slip.id),
                    ("input_type_id", "=", t.id),
                ], limit=1)

                values = {"payslip_id": slip.id, "input_type_id": t.id, "amount": amount}

                # Asignar sección según categoría del tipo
                if t.penta_category == "income":
                    values["penta_section"] = "income_fixed"
                elif t.penta_category == "deduction":
                    values["penta_section"] = "deduction_fixed"

                if line:
                    line.write(values)   # sobre-escribe
                else:
                    # no duplicar: creamos sólo si hay algo distinto de 0, o crea 0 por consistencia
                    self.env["hr.payslip.input"].create(values)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Importación completada"),
                "message": _("Se actualizaron las novedades del lote %s") % (self.run_id.name,),
                "sticky": False,
                "type": "success",
            },
        }
