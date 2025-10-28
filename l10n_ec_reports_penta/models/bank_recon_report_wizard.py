# -*- coding: utf-8 -*-
import io
import base64
from datetime import datetime, date
from calendar import monthrange

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


def _last_day(d: date) -> date:
    return d.replace(day=monthrange(d.year, d.month)[1])


class AccountAccount(models.Model):
    _inherit = 'account.account'
    hide_in_report = fields.Boolean(string="Ocultar en reporte", default=False)


class PentaBankReconReportWizard(models.TransientModel):
    _name = "penta.bank.recon.report.wizard"
    _description = "Wizard: Reporte de Conciliación Bancaria"

    date_from = fields.Date(string="Fecha desde", required=True,
                            default=lambda self: _first_day_of_current_month(self.env))
    date_to = fields.Date(string="Fecha hasta", required=True,
                          default=lambda self: fields.Date.context_today(self))
    journal_id = fields.Many2one("account.journal", string="Banco / Diario", required=True,
                                 domain="[('type', '=', 'bank')]")
    user_id = fields.Many2one("res.users", string="Usuario",
                              default=lambda self: self.env.user, readonly=True)
    account_number = fields.Char(string="Número de cuenta",
                                 compute="_compute_account_number", readonly=True)

    @api.depends("journal_id")
    def _compute_account_number(self):
        for w in self:
            acc = w.journal_id.bank_account_id
            w.account_number = acc.acc_number if acc else ""

    # ------------------ Validaciones y dataset ------------------
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
        domain = self._get_domain_move_lines()
        amls = self.env["account.move.line"].sudo().search(domain, order="date asc, id asc")

        # Si no hay datos, avisamos con pistas útiles
        if not amls:
            raise UserError(
                "No se encontraron apuntes para los filtros seleccionados.\n\n"
                "Verifica:\n"
                "1) Diario tipo Banco seleccionado y con asientos 'Publicados' en el rango.\n"
                "2) Los apuntes provengan de pagos (payment_id ≠ vacío).\n"
                "3) Las CUENTAS contables usadas en esos apuntes tengan marcado 'Ocultar en reporte'.\n"
                "   (Menú: Contabilidad → Configuración → Plan contable → editar cuenta y marcar la casilla)."
            )
        return amls

    # ------------------ Presentación ------------------
    def _is_reconciled(self, aml):
        if getattr(aml, "statement_line_id", False):
            return True
        if getattr(aml, "is_reconciled", False):
            return True
        pay = getattr(aml, "payment_id", False)
        if pay and hasattr(pay, "is_reconciled"):
            return bool(pay.is_reconciled)
        return False

    def _payment_method_name(self, aml):
        pay = aml.payment_id
        if pay and pay.payment_method_line_id:
            return (pay.payment_method_line_id.name or "").strip()
        return ""

    def _movement_type(self, aml):
        name = self._payment_method_name(aml)
        if "cheque" in name.lower():
            return "Cheque"
        if "depósito" in name.lower() or "deposito" in name.lower():
            return "Depósito"
        return name or "Pago"

    def _memo(self, aml):
        return aml.move_id.ref or aml.name or (aml.payment_id and aml.payment_id.ref) or ""

    # ------------------ Resumen extra ------------------
    def _get_statement_end_balance(self):
        """Preferimos el estado de cuenta cuyo date == fin de mes de date_to; si no, el último <= date_to."""
        self.ensure_one()
        AbSt = self.env["account.bank.statement"].sudo()
        eom = _last_day(self.date_to)
        st = AbSt.search([("journal_id", "=", self.journal_id.id),
                          ("date", "=", eom)], limit=1)
        if not st:
            st = AbSt.search([("journal_id", "=", self.journal_id.id),
                              ("date", "<=", self.date_to)], order="date desc", limit=1)
        return st.balance_end_real if st else None

    def _compute_in_transit(self, amls):
        """
        - Cheques girados y no cobrados: SUMA de credit (haber) de líneas con método 'Cheque' y NO conciliadas.
        - Depósitos/Transferencias en tránsito: SUMA de debit (debe) de líneas con método 'Depósito' y NO conciliadas.
        """
        cheques_no_cobrados = 0.0
        depositos_transito = 0.0
        for aml in amls:
            mt = self._movement_type(aml)  # basado en payment_method_line_id.name
            if not self._is_reconciled(aml):
                if mt == "Cheque":
                    cheques_no_cobrados += float(aml.credit or 0.0)  # SOLO HABER
                elif mt == "Depósito":
                    depositos_transito += float(aml.debit or 0.0)    # SOLO DEBE
        return cheques_no_cobrados, depositos_transito

    # ------------------ Data para Excel/PDF ------------------
    def _compute_table_data(self):
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

        saldo_final = rows[-1]["saldo"] if rows else 0.0
        saldo_según_extracto = self._get_statement_end_balance()
        chq_nc, dep_transito = self._compute_in_transit(amls)

        header_info = {
            "company": self.env.company.display_name or "",
            "desde": format_date(self.env, self.date_from),
            "hasta": format_date(self.env, self.date_to),
            "usuario": self.user_id.display_name,
            "diario": self.journal_id.display_name or "",
            "cuenta": self.account_number or "",
            "titulo": _("REPORTE DE CONCILIACIÓN BANCARIA"),
        }

        summary = {
            "saldo_final": saldo_final,
            "saldo_extracto": saldo_según_extracto,
            "cheques_no_cobrados": chq_nc,
            "depositos_transito": dep_transito,
        }
        return rows, summary, header_info

    # ------------------ Excel ------------------
    def action_export_xlsx(self):
        self._validate_dates()
        if not xlsxwriter:
            raise UserError(_("No se encontró 'xlsxwriter'."))
        rows, summary, header_info = self._compute_table_data()

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
        fmt_dash = wb.add_format({"italic": True, "align": "right"})

        ws = wb.add_worksheet(_("Conciliación"))
        row = 0

        # Título
        ws.write(row, 0, header_info["titulo"], fmt_title)
        row += 2

        # Cabecera
        for lbl, val in [
            (_("Compañía"), header_info["company"]),
            (_("Desde"), header_info["desde"]),
            (_("Hasta"), header_info["hasta"]),
            (_("Usuario"), header_info["usuario"]),
            (_("Diario"), header_info["diario"]),
            (_("N.º de Cuenta"), header_info["cuenta"]),
        ]:
            ws.write(row, 0, lbl, fmt_sub)
            ws.write(row, 1, val or "", fmt_text)
            row += 1

        row += 1

        # Encabezados
        headers = [_("Fecha"), _("Tipo de Movimiento"), _("Número de Documento"),
                   _("Referencia Contable"), _("Debe"), _("Haber"),
                   _("Saldo"), _("Estado de Conciliación"), _("Memo")]
        for c, h in enumerate(headers):
            ws.write(row, c, h, fmt_header_bg)
        widths = [12, 20, 20, 28, 14, 14, 14, 22, 36]
        for i, w in enumerate(widths):
            ws.set_column(i, i, w)
        row += 1

        # Cuerpo
        for r in rows:
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

        # --------- RESUMEN (negrita + líneas nuevas) ---------
        row += 1
        ws.write(row, 0, _("Resumen"), fmt_bold); row += 1

        ws.write(row, 0, _("Saldo contable final"), fmt_bold)
        ws.write_number(row, 1, summary["saldo_final"], fmt_bold_number)
        row += 1

        ws.write(row, 0, _("Saldo según extracto"), fmt_bold)
        if summary["saldo_extracto"] is None:
            ws.write(row, 1, _("(sin estado de cuenta)"), fmt_dash)
        else:
            ws.write_number(row, 1, summary["saldo_extracto"], fmt_bold_number)
        row += 1

        ws.write(row, 0, _("Cheques girados y no cobrados"), fmt_bold)
        ws.write_number(row, 1, summary["cheques_no_cobrados"], fmt_bold_number)
        row += 1

        ws.write(row, 0, _("Depósitos/Transferencias en tránsito"), fmt_bold)
        ws.write_number(row, 1, summary["depositos_transito"], fmt_bold_number)

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

    # ------------------ PDF------------------
    def action_print_pdf(self):
        self._validate_dates()
        self.ensure_one()

        # 0) Si conoces el XMLID exacto de la ACCIÓN, prueba primero (opcional)
        for xid in (
            "l10n_ec_reports_penta.report_penta_bank_recon_pdf",
        ):
            try:
                rep = self.env.ref(xid)
                if rep._name == "ir.actions.report":
                    return rep.report_action(self)
            except ValueError:
                pass  # seguimos con los fallbacks

        # 1) Buscar la acción por nombre técnico de plantilla, sin asumir prefijo de módulo
        #    (report_name es el 'name' del <report>, que debe apuntar al id de la plantilla)
        report = self.env["ir.actions.report"].search([
            ("model", "=", "penta.bank.recon.report.wizard"),
            ("report_type", "=", "qweb-pdf"),
            ("report_name", "like", "report_penta_bank_recon_pdf_template"),
        ], limit=1)
        if report:
            return report.report_action(self)

        # 2) Plan C: localizar la acción por xmlid sin conocer el módulo
        imd = self.env["ir.model.data"].search([
            ("model", "=", "ir.actions.report"),
            ("name", "=", "report_penta_bank_recon_pdf"),
        ], limit=1)
        if imd and imd.res_id:
            report = self.env["ir.actions.report"].browse(imd.res_id)
            return report.report_action(self)

        # 3) Mensaje claro si nada de lo anterior existe
        raise UserError(_(
            "No se encontró la acción de reporte PDF.\n"
            "Asegura que:\n"
            "- data/report_action.xml tenga <report id='report_penta_bank_recon_pdf' "
            "  name='<prefijo_modulo>.report_penta_bank_recon_pdf_template'>\n"
            "- reports/report_bank_recon_pdf.xml tenga <template id='report_penta_bank_recon_pdf_template'>\n"
            "- Ambos archivos estén listados en __manifest__.py, y el menú se cargue al final."
        ))



    def get_report_values_for_pdf(self):
        rows, summary, header = self._compute_table_data()
        return {
            "header": header,
            "rows": rows,
            "summary": summary,
            "company": self.env.company,
        }
