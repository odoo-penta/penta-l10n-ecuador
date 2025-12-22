# -*- coding: utf-8 -*-
import base64
import io
from odoo import fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError
from odoo.tools.misc import xlsxwriter


class PentaVacationBulkAdjustWizard(models.TransientModel):
    _name = "penta.vacation.bulk.adjust.wizard"
    _description = "Carga masiva de vacaciones: restar por 'Días tomados'"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
    )
    import_file = fields.Binary(string="Archivo Excel a importar")
    import_filename = fields.Char(string="Nombre del archivo")
    dry_run = fields.Boolean(string="Simular sin aplicar", default=True)

    # Resultado / Log
    log_text = fields.Text(string="Log de validación/aplicación", readonly=True)
    log_file = fields.Binary(string="Archivo de errores (TXT)", readonly=True)
    log_filename = fields.Char(string="Nombre log", default="vacaciones_errores.txt")

    # --------------------------- Resolver tipo de vacaciones ---------------------------
    def _resolve_leave_type(self):
        """Determina el tipo de 'vacaciones' sin pedirlo, tolerante a versiones."""
        IrConfig = self.env["ir.config_parameter"].sudo()
        LeaveType = self.env["hr.leave.type"].sudo()

        # 0) xmlid por parámetro
        xmlid = IrConfig.get_param("penta.vacations.default_leave_type_xmlid")
        if xmlid:
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec and rec._name == "hr.leave.type":
                return rec

        # 1) Dominio base
        domain = [("active", "=", True)]
        lt_fields = LeaveType._fields
        if "time_type" in lt_fields:
            domain.append(("time_type", "=", "leave"))
        if "request_unit" in lt_fields: 
            domain.append(("request_unit", "=", "day"))
        if "allocation_type" in lt_fields:
            domain.append(("allocation_type", "in", ["no", "fixed", "accrual"]))

        # 2) Por nombre
        lt = LeaveType.search(domain + [("name", "ilike", "vacac")], order="name", limit=1)
        if not lt:
            lt = LeaveType.search(domain + [("name", "ilike", "vacation")], order="name", limit=1)
        if not lt:
            lt = LeaveType.search(domain, order="name", limit=1)

        if not lt:
            raise UserError(
                "No se pudo determinar el tipo de vacaciones.\n"
                "Cree un tipo de ausentismo de vacaciones activo por días, "
                "o configure el parámetro 'penta.vacations.default_leave_type_xmlid' con su XMLID."
            )
        return lt

    # --------------------------- Helpers de saldo ---------------------------
    def _get_current_balance(self, employee, leave_type):
        """Saldo = asignaciones validadas - ausencias validadas (en días)."""
        Allocation = self.env["hr.leave.allocation"].sudo()
        Leave = self.env["hr.leave"].sudo()

        # Filtrar por compañía
        alloc_domain = [
            ("state", "=", "validate"),
            ("employee_id", "=", employee.id),
            ("holiday_status_id", "=", leave_type.id),
            ("employee_id.company_id", "=", self.company_id.id),
        ]
        alloc_days = sum(Allocation.search(alloc_domain).mapped("number_of_days"))

        leave_domain = [
            ("state", "=", "validate"),
            ("employee_id", "=", employee.id),
            ("holiday_status_id", "=", leave_type.id),
            ("employee_id.company_id", "=", self.company_id.id),
        ]
        leave_fields = Leave._fields
        if "request_unit" in leave_fields:
            leave_domain.append(("request_unit", "=", "day"))
        elif "leave_type_request_unit" in leave_fields:
            leave_domain.append(("leave_type_request_unit", "=", "day"))

        taken_days = sum(Leave.search(leave_domain).mapped("number_of_days"))
        return float(alloc_days) - float(taken_days)

    def _create_negative_adjustment(self, employee, leave_type, days_to_take):
        """Resta saldo creando una asignación NEGATIVA (seguro y auditable)."""
        Allocation = self.env["hr.leave.allocation"].sudo()
        vals = {
            "name": "Ajuste masivo: días tomados (%s)" % fields.Date.context_today(self),
            "employee_id": employee.id,
            "holiday_status_id": leave_type.id,
            "number_of_days": -abs(days_to_take),  # restar
            "state": "confirm",
            "reason": "Carga masiva de 'Días tomados' desde plantilla.",
        }
        alloc = Allocation.create(vals)
        if hasattr(alloc, "action_approve"):
            try:
                alloc.action_approve()
            except Exception:
                pass
        if hasattr(alloc, "action_validate"):
            try:
                alloc.action_validate()
            except Exception:
                pass
        return alloc

    # --------------------------- Descargar plantilla ---------------------------
    def action_download_template(self):
        leave_type = self._resolve_leave_type()
        if not xlsxwriter:
            raise UserError("No se encontró xlsxwriter en el servidor.")

        Employee = self.env["hr.employee"].sudo()
        employees = Employee.search([
            ("company_id", "=", self.company_id.id),
            ("active", "=", True)
        ], order="name")

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})
        ws = wb.add_worksheet("Plantilla")
        fmt_header = wb.add_format({"bold": True, "bg_color": "#E6F2FF", "border": 1, "align": "center"})
        fmt_text = wb.add_format({"border": 1})
        fmt_num = wb.add_format({"border": 1, "num_format": "#,##0.00"})

        headers = ["Employee ID", "Empleado", "Identificación", "Contrato", "Días disponibles (días)", "Días tomados (nuevo)"]
        for c, h in enumerate(headers):
            ws.write(0, c, h, fmt_header)
        ws.set_column(0, 0, 12)
        ws.set_column(1, 1, 28)
        ws.set_column(2, 3, 18)
        ws.set_column(4, 5, 22)

        row = 1
        for emp in employees:
            current = self._get_current_balance(emp, leave_type)
            ws.write(row, 0, emp.id, fmt_text)
            ws.write(row, 1, emp.name or "", fmt_text)
            ws.write(row, 2, emp.identification_id or "", fmt_text)
            ws.write(row, 3, emp.contract_id.name or "", fmt_text)
            ws.write_number(row, 4, current, fmt_num)     # DÍAS DISPONIBLES
            ws.write(row, 5, "", fmt_text)                # DÍAS TOMADOS
            row += 1

        wb.close()
        data = output.getvalue()
        output.close()

        fname = "plantilla_dias_tomados_%s.xlsx" % fields.Date.context_today(self)
        attach = self.env["ir.attachment"].create({
            "name": fname,
            "type": "binary",
            "datas": base64.b64encode(data),
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "res_model": self._name,
            "res_id": self.id,
        })
        return {"type": "ir.actions.act_url", "url": "/web/content/%s?download=1" % attach.id, "target": "self"}

    # --------------------------- Importar y restar ---------------------------
    def action_import_and_apply(self):
        self.ensure_one()

        if not self.import_file:
            raise UserError(_("Primero sube el Excel con la columna 'Días tomados (nuevo)'. Usa la plantilla descargada."))

        leave_type = self._resolve_leave_type()

        try:
            import pandas as pd  # type: ignore
        except Exception:
            raise UserError(_("Este servidor no tiene 'pandas'. Instálalo para poder leer Excel."))

        import base64, tempfile, unicodedata
        content = base64.b64decode(self.import_file)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=True) as tmp:
            tmp.write(content)
            tmp.flush()
            try:
                df = pd.read_excel(tmp.name, sheet_name=0)
            except Exception as e:
                raise UserError(_("No se pudo leer el Excel: %s") % e)

        def norm(s):
            s = str(s or "")
            s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
            return " ".join(s.strip().lower().split())

        df.columns = [norm(c) for c in df.columns]

        COLS = {
            "emp_id": "employee id",
            "emp_name": "empleado",
            "ident": "identificacion",
            "contract": "contrato",
            "available": "dias disponibles (dias)",
            "taken": "dias tomados (nuevo)",
        }

        missing = [v for v in COLS.values() if v not in df.columns]
        if missing:
            found = ", ".join(df.columns)
            raise UserError(_("Faltan columnas obligatorias en el Excel.\nFaltan: %s\nEncontradas: %s") %
                            (", ".join(missing), found))

        errors, applied, checked = [], 0, 0
        Employee = self.env["hr.employee"].sudo()

        def log(msg):
            errors.append(msg)

        # 👇 NO USAR "_" AQUÍ
        for idx, row in df.iterrows():
            checked += 1

            emp = False
            emp_id_val = row.get(COLS["emp_id"])
            if pd.notna(emp_id_val):
                try:
                    emp = Employee.search([("id", "=", int(emp_id_val))], limit=1)
                except Exception:
                    emp = False
            if not emp:
                ident_val = row.get(COLS["ident"])
                if pd.notna(ident_val) and str(ident_val).strip():
                    emp = Employee.search([("identification_id", "=", str(ident_val).strip())], limit=1)

            if not emp:
                log(f"[Fila {checked}] Empleado no encontrado (id={emp_id_val}, ident={row.get(COLS['ident'])}).")
                continue

            taken_raw = row.get(COLS["taken"])
            if taken_raw in (None, "", " "):
                continue
            try:
                days_taken = float(taken_raw)
            except Exception:
                log(f"[{emp.name}] Valor inválido en 'Días tomados (nuevo)': {taken_raw!r}")
                continue
            if days_taken < 0:
                log(f"[{emp.name}] 'Días tomados' no puede ser negativo: {days_taken}")
                continue

            current = self._get_current_balance(emp, leave_type)
            if days_taken > current + 1e-6:
                log(f"[{emp.name}] Días tomados ({days_taken}) excede el disponible ({current}). No se aplicó.")
                continue

            if not self.dry_run:
                try:
                    self._create_negative_adjustment(emp, leave_type, days_taken)
                    applied += 1
                except Exception as e:
                    log(f"[{emp.name}] No se pudo restar {days_taken} día(s). Error: {e}")

        stamp = fields.Datetime.now()
        header = ("Simulación" if self.dry_run else "Aplicación") + f" {stamp}\n" \
                f"Tipo de vacaciones usado: {leave_type.display_name}\n" \
                f"Compañía: {self.company_id.display_name}\n" \
                f"Filas leídas: {checked} | Ajustes aplicados: {applied}\n"
        if errors:
            header += f"Errores/Observaciones: {len(errors)}\n"
        full_log = header + ("\n".join(errors) if errors else "\nSin errores.")

        import base64 as b64
        self.log_text = full_log
        self.log_file = b64.b64encode(full_log.encode("utf-8"))
        self.log_filename = "vacaciones_log_%s.txt" % fields.Date.context_today(self)

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "name": _("Resultado de carga masiva de vacaciones"),
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
