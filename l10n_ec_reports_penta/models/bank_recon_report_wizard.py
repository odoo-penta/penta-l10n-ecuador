# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
import base64
import io
import logging
_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except Exception:
    xlsxwriter = None


class PentaBankReconReportWizard(models.TransientModel):
    _name = 'penta.bank.recon.report.wizard'
    _description = 'Reporte de Conciliación Bancaria (Tarjetas / Extracto / Pendientes)'

    # --------------------------- CAMPOS ---------------------------
    company_id = fields.Many2one(
        'res.company', string='Compañía',
        default=lambda self: self.env.company, required=True, readonly=True
    )
    date_from = fields.Date(
        string='Desde', required=True,
        default=lambda self: fields.Date.to_date(fields.Date.context_today(self)).replace(day=1)
    )
    date_to = fields.Date(
        string='Hasta', required=True,
        default=lambda self: fields.Date.context_today(self)
    )
    journal_id = fields.Many2one(
        'account.journal', string='Diario (Banco)',
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
        required=True
    )

    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        readonly=True
    )
    account_number = fields.Char(
        string='N.º de Cuenta',
        compute='_compute_account_number',
        readonly=True
    )

    @api.depends('journal_id')
    def _compute_account_number(self):
        for w in self:
            bn = ''
            if w.journal_id and w.journal_id.bank_account_id:
                acc = w.journal_id.bank_account_id
                tipo = (acc.acc_type or '').upper()
                num = acc.acc_number or ''
                bn = f'{tipo} {num}'.strip()
            w.account_number = bn

    # --------------------------- VALIDACIONES ---------------------------
    def _validate_dates(self):
        self.ensure_one()
        _logger.debug("[WIZ] Validando fechas: date_from=%s, date_to=%s", self.date_from, self.date_to)
        if self.date_from > self.date_to:
            raise UserError(_("La fecha 'Desde' no puede ser mayor que la fecha 'Hasta'."))

    # --------------------------- DOMINIOS/Lecturas BASE ---------------------------
    def _get_st_line_domain(self):
        """ Líneas de extracto del diario en el rango. """
        self.ensure_one()
        domain = [
            ('statement_id.journal_id', '=', self.journal_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        _logger.debug("[WIZ] Dominio de bank.statement.line: %s", domain)
        return domain

    def _get_statement_lines_in_range(self):
        domain = self._get_st_line_domain()
        st_lines = self.env['account.bank.statement.line'].sudo().search(domain, order='date asc, id asc')
        _logger.info("[WIZ] Encontradas %s líneas de extracto en rango [%s .. %s] para journal_id=%s",
                     len(st_lines), self.date_from, self.date_to, self.journal_id.id)
        if st_lines:
            _logger.debug("[WIZ] Primeras líneas de extracto IDs: %s", st_lines[:5].ids)
        return st_lines

    # --------------------------- SALDO EN EJECUCIÓN ---------------------------
    def _compute_running_balances(self, st_lines):
        """
        Calcula running balance por extracto:
        balance_start/balance_start_real + sum(amount) siguiendo el orden.
        """
        rb_map = {}
        if not st_lines:
            _logger.debug("[WIZ] _compute_running_balances: no hay líneas.")
            return rb_map

        for st in st_lines.mapped('statement_id'):
            lines_all = st.line_ids.sorted(key=lambda l: (l.date, l.id))
            bal_init = (st.balance_start or getattr(st, 'balance_start_real', 0.0) or 0.0)
            _logger.debug("[WIZ] Statement %s: balance_start=%s, balance_start_real=%s -> usado=%s (total líneas=%s)",
                          st.id, st.balance_start, getattr(st, 'balance_start_real', None), bal_init, len(lines_all))
            bal = bal_init
            for l in lines_all:
                bal += (l.amount or 0.0)
                rb_map[l.id] = bal

        _logger.debug("[WIZ] _compute_running_balances: map size=%s", len(rb_map))
        return rb_map

    def _get_initial_bank_balance(self):
        st_first = self.env['account.bank.statement.line'].sudo().search([
            ('statement_id.journal_id', '=', self.journal_id.id),
            ('date', '=', self.date_from),
        ], order='date asc, id asc', limit=1)
        _logger.debug("[WIZ] _get_initial_bank_balance: primera línea en %s -> %s", self.date_from, st_first and st_first.id)
        if not st_first:
            return 0.0
        val = self._compute_running_balances(st_first).get(st_first.id, 0.0)
        _logger.debug("[WIZ] _get_initial_bank_balance: valor=%s", val)
        return val

    def _get_final_bank_balance(self):
        st_last = self.env['account.bank.statement.line'].sudo().search([
            ('statement_id.journal_id', '=', self.journal_id.id),
            ('date', '=', self.date_to),
        ], order='date desc, id desc', limit=1)
        _logger.debug("[WIZ] _get_final_bank_balance: última línea en %s -> %s", self.date_to, st_last and st_last.id)
        if not st_last:
            return 0.0
        val = self._compute_running_balances(st_last).get(st_last.id, 0.0)
        _logger.debug("[WIZ] _get_final_bank_balance: valor=%s", val)
        return val

    # --------------------------- MAPEOS ---------------------------
    def _payment_from_move(self, move):
        if not move:
            return self.env['account.payment']
        pay = self.env['account.payment'].sudo().search([('move_id', '=', move.id)], limit=1)
        _logger.debug("[WIZ] _payment_from_move: move_id=%s -> payment_id=%s", move.id if move else None, pay and pay.id)
        return pay

    def _map_st_line_to_row(self, st_line, rb_map):
        move = st_line.move_id
        pay = self._payment_from_move(move)

        amt = st_line.amount or 0.0
        debe = amt if amt > 0 else 0.0
        haber = abs(amt) if amt < 0 else 0.0

        tipo_mov = getattr(st_line, 'transaction_type', False) or (st_line.payment_ref or st_line.name or 'Transacción bancaria')
        numero_doc = pay.name or ''
        numero_pago = pay.name or ''
        ref_cont = (move and (move.ref or move.name)) or ''
        estado = 'Conciliado' if st_line.move_id else 'No conciliado'
        memo = (
            (pay and (pay.payment_reference or getattr(pay, 'communication', False) or pay.name))
            or (st_line.payment_ref or st_line.name or st_line.ref)
            or (move and (move.ref or getattr(move, 'narration', False)))
            or ''
        )
        saldo = rb_map.get(st_line.id, 0.0)

        row = {
            'fecha': fields.Date.to_string(st_line.date),
            'tipo_mov': tipo_mov,
            'numero_doc': numero_doc,
            'numero_pago': numero_pago,
            'ref_cont': ref_cont,
            'debe': round(debe, 2),
            'haber': round(haber, 2),
            'saldo': round(saldo, 2),
            'estado': estado,
            'memo': memo,
        }
        _logger.debug("[WIZ] Mapeada st_line %s -> row=%s", st_line.id, row)
        return row

    def _get_body_rows_from_statement(self):
        """ Sección 1 (cuerpo): extrae de account.bank.statement.line en el rango. """
        st_lines = self._get_statement_lines_in_range()
        if not st_lines:
            _logger.info("[WIZ] No hay líneas de extracto para el rango dado.")
            return []
        rb_map = self._compute_running_balances(st_lines)
        rows = [self._map_st_line_to_row(l, rb_map) for l in st_lines]
        _logger.info("[WIZ] Sección 1 (extracto): filas=%s", len(rows))
        return rows

    # --------------------------- SECCIÓN 2: PENDIENTES ---------------------------
    def _pending_section_rows(self, direction):
        self.ensure_one()
        AML = self.env['account.move.line'].sudo()
        Pay = self.env['account.payment'].sudo()
        journal = self.journal_id
        company = self.company_id

        # 1) Cuentas outstanding EXACTAS del diario (igual que el reporte)
        accounts = (journal._get_journal_inbound_outstanding_payment_accounts()
                    + journal._get_journal_outbound_outstanding_payment_accounts())

        account_ids = accounts.ids
        _logger.info("[SEC2] cuentas outstanding=%s", account_ids)

        rows = []

        if account_ids:
            # 2) Dominio calcado del reporte (ver handler del Bank Reconciliation)
            dom = [
                ('company_id', '=', company.id),
                ('journal_id', '=', journal.id),
                ('account_id', 'in', account_ids),   # <- aquí el cambio
                ('parent_state', '=', 'posted'),
                ('display_type', '=', False),
                ('statement_line_id', '=', False),
                ('reconciled', '=', False),
                ('date', '<=', self.date_to),
            ]
            ml = AML.search(dom, order='date asc, id asc')
            _logger.info("[SEC2] ML outstanding encontrados: %s", len(ml))

            # 3) Partir por IN/OUT según balance (idéntico al reporte)
            if direction == 'in':
                ml = ml.filtered(lambda l: l.balance > 0)
            else:
                ml = ml.filtered(lambda l: l.balance < 0)

            _logger.info("[SEC2] ML dir=%s: %s", direction, len(ml))

            # 4) Agrupar por move y construir filas
            by_move = {}
            for l in ml:
                by_move.setdefault(l.move_id, []).append(l)

            for move, lines in by_move.items():
                pay = Pay.search([('move_id', '=', move.id)], limit=1)
                metodo = (pay.payment_method_line_id.name if pay.payment_method_line_id else 'Método')
                numero = pay.name or move.name or ''
                ref_cont = move.ref or move.name or ''
                memo = pay.payment_reference or getattr(pay, 'communication', False) or ref_cont or ''

                balance_sum = sum(x.balance for x in lines)
                debe = balance_sum if balance_sum > 0 else 0.0
                haber = -balance_sum if balance_sum < 0 else 0.0

                rows.append({
                    'fecha': fields.Date.to_string(move.date),
                    'tipo_mov': metodo,
                    'numero_doc': numero,
                    'numero_pago': numero,
                    'ref_cont': ref_cont,
                    'debe': round(debe, 2),
                    'haber': round(haber, 2),
                    'saldo': 0.0,
                    'estado': 'Pendiente',
                    'memo': memo or (lines[0].name or ''),
                })

        # 5) fallback a account.payment
        if not rows:
            _logger.warning("[SEC2] Sin ML outstanding; fallback a account.payment (dir=%s)", direction)
            pay_domain = [
                ('company_id', '=', company.id),
                ('state', 'in', ('posted', 'sent', 'reconciled')),
                ('date', '<=', self.date_to),
                ('payment_type', '=', 'inbound' if direction == 'in' else 'outbound'),
                ('journal_id', '=', journal.id),
            ]
            for pay in Pay.search(pay_domain, order='date asc, id asc'):
                move = pay.move_id
                if not move or move.state != 'posted':
                    continue
                # Solo líneas en cuentas outstanding y no reconciliadas
                liquidity_lines = move.line_ids.filtered(
                    lambda ml: ml.account_id.id in account_ids and not ml.full_reconcile_id and (ml.amount_residual_currency or 0.0) != 0.0
                )
                if not liquidity_lines:
                    continue

                bal = sum(ml.balance for ml in liquidity_lines)
                if direction == 'in' and bal <= 0:
                    continue
                if direction == 'out' and bal >= 0:
                    continue

                metodo = (pay.payment_method_line_id.name if pay.payment_method_line_id else 'Método')
                numero = pay.name or ''
                ref_cont = move.ref or move.name or ''
                memo = pay.payment_reference or getattr(pay, 'communication', False) or ref_cont or ''

                rows.append({
                    'fecha': fields.Date.to_string(pay.date),
                    'tipo_mov': metodo,
                    'numero_doc': numero,
                    'numero_pago': numero,
                    'ref_cont': ref_cont,
                    'debe': round(bal if bal > 0 else 0.0, 2),
                    'haber': round(-bal if bal < 0 else 0.0, 2),
                    'saldo': 0.0,
                    'estado': 'Pendiente',
                    'memo': memo,
                })

        _logger.info("[SEC2] Filas finales dir=%s: %s", direction, len(rows))
        return rows

    def _pending_group_by_method_totals(self, rows):
        buckets = {}
        for r in rows:
            k = r.get('tipo_mov') or 'Método'
            b = buckets.setdefault(k, {'debe': 0.0, 'haber': 0.0})
            b['debe'] += r.get('debe', 0.0)
            b['haber'] += r.get('haber', 0.0)
        res = [{'metodo': k, 'debe': round(v['debe'], 2), 'haber': round(v['haber'], 2)} for k, v in buckets.items()]
        _logger.debug("[WIZ][SEC2] Totales por método: %s", res)
        return res

    # --------------------------- PARA PDF/XLSX ---------------------------
    def get_report_values(self):
        """
        MISMA fuente para PDF y XLSX:
        - Sección 1 (extracto)
        - Sección 2 (pagos/cobros pendientes) con títulos fijos
        - Resumenes (saldos)
        """
        self.ensure_one()
        self._validate_dates()

        _logger.info("[WIZ] Generando valores de reporte para company=%s, journal=%s, desde=%s, hasta=%s",
                     self.company_id.id, self.journal_id.id, self.date_from, self.date_to)

        body_rows = self._get_body_rows_from_statement()

        saldo_banco_inicial = self._get_initial_bank_balance()
        saldo_banco_final = self._get_final_bank_balance()
        saldo_contable_fin = body_rows[-1]['saldo'] if body_rows else 0.0

        pagos_pend = self._pending_section_rows('out')
        cobros_pend = self._pending_section_rows('in')

        _logger.info("[WIZ] Sección 1 filas=%s | Sección 2 pagos=%s cobros=%s | Saldos: contable_fin=%s, banco_ini=%s, banco_fin=%s",
                     len(body_rows), len(pagos_pend), len(cobros_pend), saldo_contable_fin, saldo_banco_inicial, saldo_banco_final)

        return {
            'header': {
                'titulo': "REPORTE DE CONCILIACIÓN BANCARIA",
                'company': self.env.company.display_name,
                'usuario': self.env.user.display_name,
                'desde': self.date_from,
                'hasta': self.date_to,
                'diario': self.journal_id.display_name,
                'cuenta': "%s . %s %s" % (
                    self.journal_id.name or '',
                    (self.journal_id.bank_account_id and (self.journal_id.bank_account_id.acc_type or '') or '').upper(),
                    self.journal_id.bank_account_id and (self.journal_id.bank_account_id.acc_number or '') or ''
                ),
            },
            'rows': body_rows,  # Sección 1
            'section2': {
                'pagos_title': "Pagos pendientes",
                'cobros_title': "Cobros pendientes",
                'pagos': pagos_pend,
                'recibos': cobros_pend,
                'agrup_pagos': self._pending_group_by_method_totals(pagos_pend),
                'agrup_recibos': self._pending_group_by_method_totals(cobros_pend),
            },
            'summary': {
                'saldo_final': saldo_contable_fin,
                'saldo_banco_inicial': saldo_banco_inicial,
                'saldo_banco_final': saldo_banco_final,
            },
        }

    # --------------------------- BOTONES ---------------------------
    def action_print_pdf(self):
        """
        Lanza el QWeb PDF.
        """
        self.ensure_one()
        xid = "l10n_ec_reports_penta.report_penta_bank_recon_pdf"
        _logger.info("[WIZ] Lanzando PDF: ref=%s", xid)
        report = self.env.ref(xid)
        return report.report_action(self)

    # ===== Excel inline =====
    def _xls_write_headers(self, ws, row, headers, fmt_header):
        for col, h in enumerate(headers):
            ws.write(row, col, h, fmt_header)
        return row + 1

    def _xls_write_table(self, ws, row, title, rows, fmt_title, fmt_header, fmt_txt, fmt_num, with_saldo, include_num_pago=False):
        ws.write(row, 0, title, fmt_title)
        row += 1

        headers = ["Fecha", "Tipo de Movimiento", "Número de Documento"]
        keys =   ["fecha", "tipo_mov",            "numero_doc"]

        if include_num_pago:
            headers.append("Número de pago")
            keys.append("numero_pago")

        headers += ["Asiento contable", "Debe", "Haber"]
        keys    += ["ref_cont",          "debe", "haber"]

        if with_saldo:
            headers.append("Saldo")
            keys.append("saldo")

        headers += ["Estado de Conciliación", "Memo"]
        keys    += ["estado",                 "memo"]

        row = self._xls_write_headers(ws, row, headers, fmt_header)

        if not rows:
            ws.write(row, 0, "Sin resultados para los filtros seleccionados.", fmt_txt)
            return row + 2

        for r in rows:
            col = 0
            for k in keys:
                v = r.get(k, "")
                if k in ("debe", "haber", "saldo"):
                    ws.write_number(row, col, float(v or 0.0), fmt_num)
                else:
                    ws.write(row, col, v, fmt_txt)
                col += 1
            row += 1
        return row + 1

    def action_export_xlsx(self):
        """
        Genera el XLSX en memoria y lo descarga como adjunto.
        Usa exactamente los mismos datos que el PDF (get_report_values()).
        """
        self.ensure_one()
        self._validate_dates()
        if not xlsxwriter:
            raise UserError(_("No se encontró la librería 'xlsxwriter'."))

        vals = self.get_report_values()
        rows = vals.get("rows", [])
        header = vals.get("header", {})
        summary = vals.get("summary", {})
        section2 = vals.get("section2", {})
        pagos = section2.get("pagos", [])
        cobros = section2.get("recibos", [])

        _logger.info("[WIZ][XLSX] tamaños -> rows=%s, pagos=%s, cobros=%s", len(rows), len(pagos), len(cobros))

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})

        # formatos
        fmt_title = wb.add_format({"bold": True, "font_size": 14})
        fmt_header_bg = wb.add_format({"bold": True, "bg_color": "#CFE8F3", "align": "center", "valign": "vcenter", "border": 1})
        fmt_text = wb.add_format({"border": 1})
        fmt_number = wb.add_format({"num_format": "#,##0.00", "border": 1})
        fmt_bold = wb.add_format({"bold": True, "border": 1})
        fmt_bold_num = wb.add_format({"bold": True, "num_format": "#,##0.00", "border": 1})
        fmt_sub = wb.add_format({"bold": True, "bg_color": "#E7F3FA", "align": "center", "valign": "vcenter", "border": 1})

        ws = wb.add_worksheet(_("Conciliación"))
        ws.set_column(0, 0, 12)  # Fecha
        ws.set_column(1, 1, 24)  # Tipo mov
        ws.set_column(2, 3, 20)  # Nro doc / Nro pago 
        ws.set_column(4, 4, 28)  # Asiento contable
        ws.set_column(5, 7, 14)  # Debe/Haber/Saldo
        ws.set_column(8, 8, 22)  # Estado
        ws.set_column(9, 9, 36)  # Memo

        row = 0
        # Título
        ws.write(row, 0, header.get("titulo", "REPORTE DE CONCILIACIÓN BANCARIA"), fmt_title); row += 2

        # Cabecera
        cab = [
            (_("Compañía"), header.get("company", "")),
            (_("Desde"), format_date(self.env, header.get("desde"))),
            (_("Hasta"), format_date(self.env, header.get("hasta"))),
            (_("Usuario"), header.get("usuario", "")),
            (_("Diario"), header.get("diario", "")),
            (_("N.º de Cuenta"), header.get("cuenta", "")),
        ]
        for lbl, val in cab:
            ws.write(row, 0, lbl, fmt_sub)
            ws.write(row, 1, val or "", fmt_text)
            row += 1
        row += 1

        # Sección 1 – Movimientos de extracto (con Saldo)
        row = self._xls_write_table(
            ws, row, "Movimientos del extracto", rows,
            fmt_title, fmt_header_bg, fmt_text, fmt_number,
            with_saldo=True, include_num_pago=False
        )

        # Sección 2 – SIEMPRE títulos fijos
        row = self._xls_write_table(
            ws, row, section2.get("pagos_title", "Pagos pendientes"), pagos,
            fmt_title, fmt_header_bg, fmt_text, fmt_number,
            with_saldo=False, include_num_pago=True
        )
        row = self._xls_write_table(
            ws, row, section2.get("cobros_title", "Cobros pendientes"), cobros,
            fmt_title, fmt_header_bg, fmt_text, fmt_number,
            with_saldo=False, include_num_pago=True
        )

        # Resumen
        ws.write(row, 0, _("Resumen"), fmt_bold); row += 1
        ws.write(row, 0, _("Saldo contable final"), fmt_bold)
        ws.write_number(row, 1, float(summary.get("saldo_final", 0.0)), fmt_bold_num); row += 1

        if "saldo_extracto" in summary:
            val = summary.get("saldo_extracto")
            ws.write(row, 0, _("Saldo según extracto"), fmt_bold)
            if val is None:
                ws.write(row, 1, _("(sin estado de cuenta)"), fmt_text)
            else:
                ws.write_number(row, 1, float(val or 0.0), fmt_bold_num)
            row += 1

        ws.write(row, 0, _("Saldo bancario inicial"), fmt_bold)
        ws.write_number(row, 1, float(summary.get("saldo_banco_inicial", 0.0)), fmt_bold_num); row += 1

        ws.write(row, 0, _("Saldo bancario final"), fmt_bold)
        ws.write_number(row, 1, float(summary.get("saldo_banco_final", 0.0)), fmt_bold_num); row += 1

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
        _logger.info("[WIZ][XLSX] Adj creado id=%s tamaño=%s bytes", attachment.id, len(data))
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=1", "target": "self"}
