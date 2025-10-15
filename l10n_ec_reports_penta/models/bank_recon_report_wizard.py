# -*- coding: utf-8 -*-
import io
import base64
from datetime import datetime, date
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _
from odoo.tools import format_date
from odoo.tools.misc import xlsxwriter

try:
    from odoo.addons.penta_base.reports.xlsx_formats import get_xlsx_formats
except Exception:
    get_xlsx_formats = None


def _first_day_of_current_month(env):
    today = fields.Date.context_today(env.user)
    if isinstance(today, str):
        y, m, d = map(int, today.split('-'))
        today = date(y, m, d)
    return today.replace(day=1)


class AccountAccount(models.Model):
    _inherit = 'account.account'
    hide_in_report = fields.Boolean(string="Ocultar en reporte", default=False)


class PentaBankReconReportWizard(models.TransientModel):
    _name = "penta.bank.recon.report.wizard"
    _description = "Wizard: Reporte de Conciliación Bancaria"

    date_from = fields.Date(
        string="Fecha desde", required=True,
        default=lambda self: _first_day_of_current_month(self.env)
    )
    date_to = fields.Date(
        string="Fecha hasta", required=True,
        default=lambda self: fields.Date.context_today(self)
    )
    journal_id = fields.Many2one(
        "account.journal", string="Banco / Diario", required=True,
        domain="[('type', '=', 'bank')]"
    )
    user_id = fields.Many2one(
        "res.users", string="Usuario", default=lambda self: self.env.user, readonly=True
    )
    account_number = fields.Char(string="Número de cuenta",
                                 compute="_compute_account_number", readonly=True)

    @api.depends("journal_id")
    def _compute_account_number(self):
        for w in self:
            acc = w.journal_id.bank_account_id  # res.partner.bank
            w.account_number = acc.acc_number if acc else ""

    # --------- Validaciones y dataset ----------
    def _validate_dates(self):
        if not self.date_from or not self.date_to:
            raise UserError(_("Debes establecer fecha de inicio y fecha fin."))
        if self.date_from > self.date_to:
            raise UserError(_("La fecha inicio no puede ser mayor a la fecha fin."))

    def _get_domain_move_lines(self):
        self.ensure_one()
        return [
            ("journal_id", "=", self.journal_id.id),
            ("parent_state", "=", "posted"),
            ("display_type", "=", False),
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
            ("payment_id", "!=", False),
            ("account_id.hide_in_report", "=", True),
        ]

    def _get_lines(self):
        return self.env["account.move.line"].sudo().search(
            self._get_domain_move_lines(),
            order="date asc, id asc"
        )

    # --------- Helpers de presentación ----------
    def _is_reconciled(self, aml):
        if getattr(aml, "statement_line_id", False):
            return True
        if getattr(aml, "is_reconciled", False):
            return True
        payment = getattr(aml, "payment_id", False)
        if payment and hasattr(payment, "is_reconciled"):
            return bool(payment.is_reconciled)
        return False

    def _movement_type(self, aml):
        pay = aml.payment_id
        if pay and pay.payment_method_line_id:
            name = (pay.payment_method_line_id.name or "").strip()
            if "cheque" in name.lower():
                return "Cheque"
            return name
        return "Pago"

    def _memo(self, aml):
        return aml.move_id.ref or aml.name or (aml.payment_id and aml.payment_id.ref) or ""

    # --------- Estructura de datos para Excel/PDF ----------
    def _compute_table_data(self):
        """
        Devuelve (rows, saldo_final, header_info)
        rows: lista de diccionarios con columnas requeridas y saldo acumulado
        """
        self.ensure_one()
        amls = self._get_lines()
        running = 0.0
        rows = []
        for aml in amls:
            debe = float(aml.debit or 0.0)
            haber = float(aml.credit or 0.0)
            running += (debe - haber)
            rows.append({
                "fecha": aml.date,
                "tipo_mov": self._movement_type(aml),
                "numero_doc": aml.move_id.name or "",
                "ref_cont": aml.name or "",
                "debe": debe,
                "haber": haber,
                "saldo": running,
                "estado": _("Conciliado") if self._is_reconciled(aml) else _("No conciliado"),
                "memo": self._memo(aml),
            })

        header_info = {
            "company": self.env.company.display_name or "",
            "desde": format_date(self.env, self.date_from),
            "hasta": format_date(self.env, self.date_to),
            "usuario": self.user_id.display_name,
            "diario": self.journal_id.display_name or "",
            "cuenta": self.account_number or "",
            "titulo": _("REPORTE DE CONCILIACIÓN BANCARIA"),
        }
        return rows, (rows[-1]["saldo"] if rows else 0.0), header_info

    # --------- Exportar Excel (con Resumen) ----------
    def action_export_xlsx(self):
        self._validate_dates()
        if not xlsxwriter:
            raise UserError(_("No se encontró 'xlsxwriter'."))
        rows, saldo_final, header_info = self._compute_table_data()

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})
        formats = {}
        if get_xlsx_formats:
            try:
                formats = get_xlsx_formats(wb) or {}
            except Exception:
                formats = {}

        fmt_title = formats.get("title") or wb.add_format({"bold": True, "font_size": 14})
        fmt_header_bg = formats.get("header_bg") or wb.add_format({"bold": True, "bg_color": "#CFE8F3", "align": "center", "valign": "vcenter", "border": 1})
        fmt_sub = formats.get("header_sub") or wb.add_format({"bold": True, "bg_color": "#E7F3FA", "align": "center", "valign": "vcenter", "border": 1})
        fmt_text = formats.get("border") or wb.add_format({"border": 1})
        fmt_date = formats.get("date") or wb.add_format({"num_format": "yyyy-mm-dd", "border": 1})
        fmt_number = formats.get("number") or wb.add_format({"num_format": "#,##0.00", "border": 1})
        fmt_bold = wb.add_format({"bold": True, "border": 1})
        fmt_bold_number = wb.add_format({"bold": True, "num_format": "#,##0.00", "border": 1})

        ws = wb.add_worksheet(_("Conciliación"))
        row = 0

        # Título
        ws.write(row, 0, header_info["titulo"], fmt_title)
        row += 2

        # Cabecera
        pairs = [
            (_("Compañía"), header_info["company"]),
            (_("Desde"), header_info["desde"]),
            (_("Hasta"), header_info["hasta"]),
            (_("Usuario"), header_info["usuario"]),
            (_("Diario"), header_info["diario"]),
            (_("N.º de Cuenta"), header_info["cuenta"]),
        ]
        for lbl, val in pairs:
            ws.write(row, 0, lbl, fmt_sub)
            ws.write(row, 1, val or "", fmt_text)
            row += 1

        row += 1

        # Encabezados tabla
        headers = [
            _("Fecha"), _("Tipo de Movimiento"), _("Número de Documento"),
            _("Referencia Contable"), _("Debe"), _("Haber"),
            _("Saldo"), _("Estado de Conciliación"), _("Memo")
        ]
        for c, h in enumerate(headers):
            ws.write(row, c, h, fmt_header_bg)
        widths = [12, 20, 20, 28, 14, 14, 14, 22, 36]
        for i, w in enumerate(widths):
            ws.set_column(i, i, w)
        row += 1

        # Cuerpo
        for r in rows:
            # Fecha
            f = r["fecha"]
            dt = datetime.combine(f, datetime.min.time()) if isinstance(f, date) and not isinstance(f, datetime) else fields.Datetime.to_datetime(f)
            ws.write_datetime(row, 0, dt, fmt_date)
            ws.write(row, 1, r["tipo_mov"], fmt_text)
            ws.write(row, 2, r["numero_doc"], fmt_text)
            ws.write(row, 3, r["ref_cont"], fmt_text)
            ws.write_number(row, 4, r["debe"], fmt_number)
            ws.write_number(row, 5, r["haber"], fmt_number)
            ws.write_number(row, 6, r["saldo"], fmt_number)
            ws.write(row, 7, r["estado"], fmt_text)
            ws.write(row, 8, r["memo"], fmt_text)
            row += 1

        # --------- RESUMEN (en negrita) ----------
        row += 1
        ws.write(row, 0, _("Resumen"), fmt_bold)
        row += 1
        ws.write(row, 0, _("Saldo contable final"), fmt_bold)
        ws.write_number(row, 1, saldo_final, fmt_bold_number)

        wb.close()
        data = output.getvalue()
        output.close()

        fname = "reporte_conciliacion_bancaria_%s_%s.xlsx" % (self.date_from, self.date_to)
        attachment = self.env["ir.attachment"].create({
            "name": fname,
            "type": "binary",
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "datas": base64.b64encode(data),
            "res_model": self._name,
            "res_id": self.id,
        })
        return {"type": "ir.actions.act_url",
                "url": f"/web/content/{attachment.id}?download=1",
                "target": "self"}

    # --------- PDF (QWeb) ----------
    def action_print_pdf(self):
        self._validate_dates()
        return self.env.ref("penta_bank_recon.report_penta_bank_recon_pdf").report_action(self)

    # Usado por el QWeb
    def get_report_values_for_pdf(self):
        rows, saldo_final, header = self._compute_table_data()
        return {
            "header": header,
            "rows": rows,
            "saldo_final": saldo_final,
            "company": self.env.company,
        }
