# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from io import BytesIO
import base64
from datetime import date, datetime
import statistics
import xlsxwriter
from odoo.addons.penta_base.reports.xlsx_formats import get_xlsx_formats
import re
from collections import OrderedDict


class PentalabReportCarteraReporteWizard(models.TransientModel):
    _name = "pentalab.report.cartera.reporte.wizard"
    _description = "Wizard para Reporte de Cartera (formato Reporte / no EBI)"

    date_end = fields.Date(string="Fecha hasta", required=True)

    file_name = fields.Char(string="Nombre de archivo", readonly=True)
    file_data = fields.Binary(string="Archivo", readonly=True)

    def action_generate_cartera_reporte(self):
        self.ensure_one()
        cutoff_date = self.date_end or date.today()

        report = self.env.ref('account_reports.aged_receivable_report')
        date_from = cutoff_date.replace(year=cutoff_date.year - 10, month=1, day=1)
        options = report.get_options(previous_options={
            'date': {
                'mode': 'range',
                'date_from': date_from.strftime('%Y-%m-%d'),
                'date_to': cutoff_date.strftime('%Y-%m-%d'),
                'filter': 'custom',
            }
        })

        options['companies'] = [
            {'id': c.id, 'name': c.name, 'currency_id': c.currency_id.id}
            for c in self.env.companies
        ]
        options['unfold_all'] = True
        options['show_account'] = True

        # === Recolectar líneas del aged (usamos la línea aml como pivote) ===
        items = []
        for line in report._get_lines(options):
            lid = line.get("id")
            if lid and 'account.move.line' in lid:
                aml_id = int(lid.split("account.move.line~")[1])
                aml = self.env['account.move.line'].browse(aml_id)
                items.append({'aml': aml})

        all_cat_map = OrderedDict()  # key: nombre lower -> valor mostrado (primera forma vista)
        for it in items:
            partner = it['aml'].partner_id
            if not partner or not partner.category_id:
                continue
            for cat in partner.category_id:
                nm = (cat.name or '').strip()
                key = nm.lower()
                if key and key not in all_cat_map:
                    all_cat_map[key] = nm

        # Si quieres orden alfabético por nombre mostrado:
        all_cat_items = sorted(all_cat_map.items(), key=lambda kv: kv[1].lower())
        dynamic_category_headers = [disp_name for _, disp_name in all_cat_items]

        # === Helpers ===
        def _days_between(d1, d2):
            if d1 and d2:
                return (fields.Date.to_date(d1) - fields.Date.to_date(d2)).days
            return 0

        def _get_line_payment_number(aml):
            txt = f"{aml.name or ''} {(getattr(aml, 'ref', '') or '')}"
            m = re.search(r'#\s*(\d+)', txt)
            return int(m.group(1)) if m else 1

        def _line_residual_amount(aml):
            return abs(aml.amount_residual or 0.0)

        def _original_line_amount(aml):
            if aml is None:
                return 0.0
            return abs(aml.balance if aml.balance is not None else (aml.debit - aml.credit))

        def _line_paid_amount(aml):
            original = _original_line_amount(aml)
            residual = _line_residual_amount(aml)
            paid = original - residual
            if paid < 0:
                paid = 0.0
            if paid > original:
                paid = original
            return paid

        def _count_total_installments_for_move(move):
            """
            Total SIN usar términos de pago.
            Escanea TODAS las líneas receivable del move:
            - 'n/m' o 'n de m' -> usa m como total
            - '#<n>'           -> n como candidato a total
            """
            if not move:
                return 1
            max_total = 0
            for l in move.line_ids:
                if not (l.account_id and l.account_id.account_type == 'asset_receivable') or l.display_type:
                    continue
                text = f"{l.name or ''} {(getattr(l, 'ref', '') or '')}"
                m1 = re.search(r'(\d+)\s*/\s*(\d+)', text)
                if m1:
                    max_total = max(max_total, int(m1.group(2)))
                m2 = re.search(r'(\d+)\s*de\s*(\d+)', text)
                if m2:
                    max_total = max(max_total, int(m2.group(2)))
                for n in re.findall(r'#\s*(\d+)', text):
                    try:
                        max_total = max(max_total, int(n))
                    except Exception:
                        pass
            return max_total or 1

        def _warehouse_from_invoice(move):
            """
            Extrae '002-001-...' desde move.name y busca el warehouse:
            - primer grupo (3 dígitos)  -> l10n_ec_emission  (punto de emisión)
            - segundo grupo (3 dígitos) -> l10n_ec_entity    (entidad emisora)
            """
            if not move:
                return (None, None)

            name = (move.name or '').strip()

            # Buscar patrón tipo 002-001-000000267
            m = re.search(r'(\d{3})-(\d{3})-\d+', name, flags=re.IGNORECASE)
            if not m:
                return (None, None)

            emission = m.group(1)  # punto de emisión
            entity = m.group(2)    # entidad emisora

            domain = [
                ('l10n_ec_emission', '=', entity),
                ('l10n_ec_entity', '=', emission),
            ]

            wh = self.env['stock.warehouse'].search(domain, limit=1)

            return (wh.id, wh.name) if wh else (None, None)

        def _bucket_edad_vencida(dias):
            """Clasifica los días vencidos en rangos solicitados.
            0 o negativo -> 'No vencido' (puedes cambiarlo si quieres tratar 0 como vencido).
            """
            if dias <= 0:
                return '0'
            if 1 <= dias <= 15:
                return '1 a 15'
            if 16 <= dias <= 30:
                return '16 a 30'
            if 31 <= dias <= 60:
                return '31 a 60'
            if 61 <= dias <= 90:
                return '61 a 90'
            if 91 <= dias <= 180:
                return '91 a 180'
            if 181 <= dias <= 360:
                return '181 a 360'
            # > 360: años
            years = (dias - 1) // 365 + 1  # 361..725 => 1, etc.
            if years >= 5:
                return 'Mas de 5 anios'
            return f'Mas de {years} anios'

        def _paid_until_cutoff(aml, cutoff_date_local):
            """
            Suma únicamente las conciliaciones (account.partial.reconcile) cuya
            contraparte tenga fecha <= cutoff_date.
            Evita doble conteo uniendo matched_debit_ids y matched_credit_ids.
            """
            if not aml:
                return 0.0
            partials = set(aml.matched_debit_ids) | set(aml.matched_credit_ids)
            total = 0.0
            for pr in partials:
                # Determina la línea contraparte del pago/cobro
                if pr.debit_move_id.id == aml.id:
                    counter_ml = pr.credit_move_id
                else:
                    counter_ml = pr.debit_move_id
                pay_date = counter_ml.date or counter_ml.move_id.date
                if pay_date and fields.Date.to_date(pay_date) <= fields.Date.to_date(cutoff_date_local):
                    total += float(pr.amount or 0.0)
            # No exceder el original
            return min(total, _original_line_amount(aml))

        def _residual_as_of(aml, cutoff_date_local):
            original = _original_line_amount(aml)
            paid = _paid_until_cutoff(aml, cutoff_date_local)
            return max(0.0, original - paid)

        def _last_payment_date_until_cutoff(aml, cutoff_date_local):
            """
            Última fecha de pago de ESTA línea, pero solo hasta cutoff_date.
            """
            dates = []
            if not aml:
                return None
            partials = set(aml.matched_debit_ids) | set(aml.matched_credit_ids)
            for pr in partials:
                counter_ml = pr.credit_move_id if pr.debit_move_id.id == aml.id else pr.debit_move_id
                d = counter_ml.date or counter_ml.move_id.date
                if d and fields.Date.to_date(d) <= fields.Date.to_date(cutoff_date_local):
                    dates.append(fields.Date.to_date(d))
            return max(dates) if dates else None

        def _pick_cliente_category(partner):
            """
            Devuelve (id, name) de la categoría que cumpla:
            1) contact_type contiene 'cliente' (si el campo existe)
            2) si no, name contiene 'cliente'
            3) si no hay match, retorna (None, None)
            """
            if not partner or not partner.category_id:
                return (None, None)

            cats = partner.category_id

            # 1) por contact_type (si existe el campo)
            for c in cats:
                ct = getattr(c, 'contact_type', False) or False
                if isinstance(ct, str) and ('cliente' in ct.strip().lower()):
                    return (c.id, c.name or 'ND')

            # 2) por name
            for c in cats:
                nm = (c.name or '').strip().lower()
                if 'cliente' in nm:
                    return (c.id, c.name or 'ND')

            # 3) sin match
            return (None, None)

        def _last_paid_installment_number(move):
            """
            Retorna la mayor cuota pagada (int) del comprobante 'move', buscando patrones '#<num>'
            en las líneas por cobrar (asset_receivable) que tengan monto pagado > 0.
            Si no encuentra nada, retorna 0.
            """
            if not move:
                return 0
            max_num = 0
            for l in move.line_ids:
                if l.account_id and l.account_id.account_type == 'asset_receivable':
                    # pagado en la línea (usamos helper existente)
                    original = abs(l.balance if l.balance is not None else (l.debit - l.credit))
                    residual = abs(l.amount_residual or 0.0)
                    paid = max(0.0, min(original, original - residual))
                    if paid > 0.0001:
                        txt = f"{l.name or ''} {(getattr(l, 'ref', '') or '')}".lower()
                        m = re.search(r'#\s*(\d+)', txt)
                        if m:
                            try:
                                num = int(m.group(1))
                                if num > max_num:
                                    max_num = num
                            except Exception:
                                pass
            return max_num

        def _ref_cod_pais_value(partner):
            """
            Devuelve el código de país para REF_COD_PAIS en modo 'Reporte':
            deja el código ISO (EC, CO, PE, MX, VE) tal como está.
            """
            code = (partner.country_id.code or '').strip().upper() if partner and partner.country_id else ''
            if not code:
                return 'ND'
            return code

        def _map_transaccion(aml_local):
            mv = aml_local.move_id
            doc_name = (mv.l10n_latam_document_type_id.name or '').strip().lower() if mv.l10n_latam_document_type_id else ''

            # 1 = Factura cliente
            if mv.move_type == 'out_invoice':
                return 1

            # 2 = Nota de crédito
            if mv.move_type == 'out_refund' or 'crédito' in doc_name or 'credito' in doc_name:
                return 2

            # 6 = Nota de débito
            if mv.move_type == 'out_debit' or 'débito' in doc_name or 'debito' in doc_name:
                return 6

            # 7 = Pago (solo si es un entry que tiene payment_id)
            if mv.move_type == 'entry':
                return 7

            # Todo lo demás se trata como factura (por defecto)
            return 1

        def _last_payment_date_line(aml):
            dates = []
            if not aml:
                return None
            for part in (aml.matched_credit_ids or self.env['account.partial.reconcile']):
                d = part.credit_move_id.date or part.credit_move_id.move_id.date
                if d:
                    dates.append(fields.Date.to_date(d))
            for part in (aml.matched_debit_ids or self.env['account.partial.reconcile']):
                d = part.debit_move_id.date or part.debit_move_id.move_id.date
                if d:
                    dates.append(fields.Date.to_date(d))
            return max(dates) if dates else None

        # === Precompute totales por move ===
        # 1) Máximo REF_CUOTA visto en los ITEMS del aged
        max_cuota_from_items = {}
        for it in items:
            aml = it['aml']
            mv = aml.move_id
            if not mv:
                continue
            n = _get_line_payment_number(aml)  # solo '#<n>'
            prev = max_cuota_from_items.get(mv.id, 0)
            if n > prev:
                max_cuota_from_items[mv.id] = n

        # 2) Total detectado en asientos (líneas receivable del move)
        totals_by_move_db = {}
        for it in items:
            aml = it['aml']
            mv = aml.move_id
            if mv and mv.id not in totals_by_move_db:
                totals_by_move_db[mv.id] = _count_total_installments_for_move(mv)

        # 3) Total final por move = max(total_db, max REF_CUOTA visto en items)
        totals_by_move = {}
        for mv_id in set(list(totals_by_move_db.keys()) + list(max_cuota_from_items.keys())):
            totals_by_move[mv_id] = max(totals_by_move_db.get(mv_id, 1), max_cuota_from_items.get(mv_id, 1))

        # === XLSX ===
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        formats = get_xlsx_formats(workbook)
        sheet = workbook.add_worksheet('Cartera')

        headers = [
            'REF_EMPRESA',
            'FECHA_DATOS',
            'CUPO_CLIENTE',
            'REF_CLI_TIPO_IDE',
            'REF_CLI_IDENTIFICACION',
            'REF_CLI_NOMBRE',
            'REF_CLI_TELEFONO',
            'REF_CLI_CELULAR',
            'REF_CLI_MAIL',
            'REF_CLI_CALLE_PRINCIPAL',
            'REF_CLI_CALLE_SECUNDARIA',
            'REF_CLI_CIUDAD',
            'REF_COD_PAIS',
            'REF_COD_PROVINCIA',
            'REF_COD_CIUDAD',
            'COD_PARROQUIA',
            'REF_DOCUMENTO',
            'REF_PLAZO',
            'REF_PERIODICIDAD',
            'REF_TRANSACCION',
            'REF_CUOTA',
            'NUM_TOTAL_CUOTA',
            'REF_VALOR',
            'REF_CANCELADO',
            'REF_SALDO',
            'REF_DOCUMENTADO',
            'REF_INTERES',
            'REF_TASA_INTERES',
            'REF_VALOR_MORA',
            'REF_DIAS_MORA',
            'SALDO_POR_VENCER',
            'SALDO_VENCIDO',
            'EDAD',
            'TIPO',
            'REF_FECHA_DOC',
            'REF_FECHA_EMI',
            'ANO',
            'MES',
            'REF_FECHA_VEN',
            'REF_FECHA_CANCELA',
            'REF_ALMACEN_ID',
            'REF_ALMACEN_NOMBRE',
            'REF_VEN_CEDULA',
            'REF_VEN_NOMBRE',
            'REF_GESTION_ID',
            'REF_GESTION_NOMBRE',
            'REF_ESTADO_ID',
            'REF_ESTADO_NOMBRE',
            'REF_CUE_ID',
            'REF_CUE_NOMBRE',
            'REF_GRU_ID',
            'REF_GRU_NOMBRE',
            'TERMINO_PAGO',
            'GARANTIA_CONTACTO',
            'ULTIMA_CUOTA_PAGADA',
        ]
        headers.extend(dynamic_category_headers)

        sheet.write(0, 0, 'Fecha de corte', formats['header_bg'])
        sheet.write(0, 1, cutoff_date.strftime('%d-%m-%Y'), formats['date'])
        for col, title in enumerate(headers):
            sheet.write(1, col, title, formats['header_bg'])
            sheet.set_column(col, col, max(len(title) + 2, 14))
        sheet.set_column(0, len(headers) - 1, 18)
        id_map = {'cédula': 1, 'cedula': 1, 'ruc': 2, 'pasaporte': 3}

        row = 2
        for it in items:
            aml = it['aml']
            partner = aml.partner_id
            move = aml.move_id
            account = aml.account_id

            # Fechas base
            fecha_venc_linea = aml.date_maturity or aml.date
            fecha_venc_factura = move.invoice_date_due if move else None
            fecha_factura = move.date if move else None

            # Cálculos
            ref_plazo_days = (
                (fecha_venc_linea - fecha_factura).days
                if fecha_factura and fecha_venc_linea else 0
            )
            edad_vencido = (_bucket_edad_vencida(
                max((cutoff_date - fecha_venc_linea).days, 0)
            ) if fecha_venc_linea and cutoff_date >= fecha_venc_linea else '0')

            ref_periodicidad_days = 0
            if fecha_factura and fecha_venc_linea:
                ref_periodicidad_days = abs((fecha_factura - fecha_venc_linea).days)
            cuota_num = _get_line_payment_number(aml)  # '#<n>' de la línea
            trans_val = _map_transaccion(aml)
            total_cuotas = 0 if trans_val == 7 else totals_by_move.get(move.id, 1)

            # 1) Base (como ya lo tienes)
            valor_original = _original_line_amount(aml)           # absoluto para cálculos
            pagado_asof = _paid_until_cutoff(aml, cutoff_date)    # absoluto
            saldo_asof = _residual_as_of(aml, cutoff_date)        # absoluto

            # 2) Signo del documento (usa el balance REAL de la línea)
            sign = 1 if float(aml.balance or 0.0) >= 0 else -1

            # 3) Versiones firmadas para el reporte
            ref_valor_signed = float(aml.balance or 0.0)          # ya viene con su signo real
            ref_cancelado_signed = sign * float(pagado_asof)
            ref_saldo_signed = sign * float(saldo_asof)           # saldo a la fecha de corte
            last_pay = _last_payment_date_until_cutoff(aml, cutoff_date)

            # Saldos por estado
            days_remaining = (fecha_venc_linea - cutoff_date).days if fecha_venc_linea else 0
            saldo_por_vencer = ref_saldo_signed if days_remaining > 0 else 0.0
            saldo_vencido = ref_saldo_signed if (fecha_venc_linea and cutoff_date >= fecha_venc_linea) else 0.0
            es_vencido = bool(fecha_venc_linea and cutoff_date >= fecha_venc_linea)
            tipo_label = 'VENCIDO' if es_vencido else 'POR VENCER'

            col = 0
            sheet.write(row, col, (aml.company_id.token_ebi if hasattr(aml.company_id, 'token_ebi') and aml.company_id.token_ebi else 'ND'), formats['border']); col += 1
            sheet.write(row, col, cutoff_date.strftime('%d-%m-%Y'), formats['date']); col += 1
            sheet.write_number(row, col, float(partner.credit_limit or 0.0), formats['number']); col += 1

            tipo_name = (partner.l10n_latam_identification_type_id.name or '').strip().lower() if partner else ''
            sheet.write(row, col, id_map.get(tipo_name, 3), formats['border']); col += 1
            sheet.write(row, col, (partner.vat or 'ND') if partner else 'ND', formats['border']); col += 1
            sheet.write(row, col, (partner.name or 'ND') if partner else 'ND', formats['border']); col += 1
            sheet.write(row, col, (partner.phone or 'ND') if partner else 'ND', formats['border']); col += 1
            sheet.write(row, col, (partner.mobile or 'ND') if partner else 'ND', formats['border']); col += 1
            sheet.write(row, col, (partner.email or 'ND') if partner else 'ND', formats['border']); col += 1
            sheet.write(row, col, (partner.street or 'ND') if partner else 'ND', formats['border']); col += 1
            sheet.write(row, col, (partner.street2 or 'ND') if partner else 'ND', formats['border']); col += 1

            ref_cli_ciudad = 'ND'
            if partner:
                if partner.city_id and partner.city_id.name:
                    ref_cli_ciudad = partner.city_id.name
                elif partner.city:
                    ref_cli_ciudad = partner.city
            sheet.write(row, col, ref_cli_ciudad, formats['border']); col += 1

            # Aquí ya NO usamos modo EBI, siempre código ISO
            sheet.write(row, col, _ref_cod_pais_value(partner), formats['border']); col += 1

            sheet.write(row, col, (partner.state_id.code if partner and partner.state_id and partner.state_id.code else 'ND'), formats['border']); col += 1
            sheet.write(row, col, (
                f"{int(partner.city_id.code):02d}" if partner and partner.city_id and partner.city_id.code not in (False, None, '') else 'ND'
            ), formats['border']); col += 1

            sheet.write(row, col, (
                f"{int(partner.parroquia_id.code):02d}" if partner and hasattr(partner, 'parroquia_id') and partner.parroquia_id and partner.parroquia_id.code not in (False, None, '') else 'ND'
            ), formats['border']); col += 1

            sheet.write(row, col, (move.name or 'ND'), formats['border']); col += 1
            sheet.write_number(row, col, int(ref_plazo_days), formats['border']); col += 1
            sheet.write_number(row, col, int(ref_periodicidad_days), formats['border']); col += 1

            sheet.write_number(row, col, trans_val, formats['border']); col += 1
            sheet.write_number(row, col, int(cuota_num), formats['border']); col += 1
            sheet.write_number(row, col, int(total_cuotas), formats['border']); col += 1

            sheet.write_number(row, col, float(aml.balance or 0.0), formats['number']); col += 1  # REF_VALOR (ORIGINAL)
            sheet.write_number(row, col, ref_cancelado_signed, formats['number']); col += 1       # REF_CANCELADO
            sheet.write_number(row, col, ref_saldo_signed, formats['number']); col += 1           # REF_SALDO
            sheet.write_number(row, col, 0.0, formats['number']); col += 1                        # REF_DOCUMENTADO
            sheet.write_number(row, col, 0.0, formats['number']); col += 1                        # REF_INTERES
            sheet.write_number(row, col, 0.0, formats['number']); col += 1                        # REF_TASA_INTERES
            sheet.write_number(row, col, 0.0, formats['number']); col += 1                        # REF_VALOR_MORA
            sheet.write_number(row, col, 0.0, formats['number']); col += 1                        # REF_DIAS_MORA

            sheet.write_number(row, col, float(saldo_por_vencer), formats['number']); col += 1    # SALDO_POR_VENCER
            sheet.write_number(row, col, float(saldo_vencido), formats['number']); col += 1       # SALDO_VENCIDO
            sheet.write(row, col, edad_vencido, formats['border']); col += 1                      # EDAD
            sheet.write(row, col, tipo_label, formats['border']); col += 1                        # TIPO

            ref_fecha_doc = move.date if move else None
            ref_fecha_emi = move.invoice_date if move else None
            sheet.write(row, col, ref_fecha_doc.strftime('%d-%m-%Y') if ref_fecha_doc else 'ND', formats['date']); col += 1
            sheet.write(row, col, ref_fecha_emi.strftime('%d-%m-%Y') if ref_fecha_emi else 'ND', formats['date']); col += 1

            if ref_fecha_doc:
                sheet.write_number(row, col, ref_fecha_doc.year, formats['date']); col += 1
                sheet.write_number(row, col, ref_fecha_doc.month, formats['date']); col += 1
            else:
                sheet.write(row, col, 'ND', formats['border']); col += 1
                sheet.write(row, col, 'ND', formats['border']); col += 1

            sheet.write(row, col, (fecha_venc_linea.strftime('%d-%m-%Y') if fecha_venc_linea else 'ND'), formats['date']); col += 1
            sheet.write(row, col, (last_pay.strftime('%d-%m-%Y') if last_pay else 'ND'), formats['border']); col += 1

            alm_id, alm_name = _warehouse_from_invoice(move) if move else (None, None)
            sheet.write(row, col, (alm_id if alm_id else 'ND'), formats['border']); col += 1      # REF_ALMACEN_ID
            sheet.write(row, col, (alm_name if alm_name else 'ND'), formats['border']); col += 1  # REF_ALMACEN_NOMBRE

            emp = move.invoice_user_id.employee_id if move else False
            sheet.write(row, col, (emp.identification_id if emp and emp.identification_id else 'ND'), formats['border']); col += 1
            sheet.write(row, col, (emp.name if emp and emp.name else 'ND'), formats['border']); col += 1

            sheet.write(row, col, 'ND', formats['border']); col += 1
            sheet.write(row, col, 'ND', formats['border']); col += 1
            sheet.write(row, col, 'ND', formats['border']); col += 1
            sheet.write(row, col, 'ND', formats['border']); col += 1

            sheet.write(row, col, (account.code or 'ND') if account else 'ND', formats['border']); col += 1
            sheet.write(row, col, (account.name or 'ND') if account else 'ND', formats['border']); col += 1

            gru_id, gru_name = _pick_cliente_category(partner)
            sheet.write(row, col, gru_id if gru_id else 'ND', formats['border']); col += 1     # REF_GRU_ID
            sheet.write(row, col, gru_name if gru_name else 'ND', formats['border']); col += 1 # REF_GRU_NOMBRE


            sheet.write(row, col, (move.invoice_payment_term_id.name if move and move.invoice_payment_term_id else 'ND'), formats['border']); col += 1  # TERMINO_PAGO

            garantia_txt = getattr(partner, 'guarantee_note', False) or 'ND'
            sheet.write(row, col, garantia_txt, formats['border']); col += 1  # GARANTIA_CONTACTO

            ultima_cuota = _last_paid_installment_number(move)
            sheet.write_number(row, col, int(ultima_cuota), formats['border']); col += 1  # ULTIMA_CUOTA_PAGADA

            partner_cat_keys = set()
            if partner and partner.category_id:
                for c in partner.category_id:
                    nm = (c.name or '').strip().lower()
                    if nm:
                        partner_cat_keys.add(nm)

            for key, header_name in all_cat_items:
                sheet.write(row, col, header_name if key in partner_cat_keys else 'ND', formats['border'])
                col += 1

            row += 1

        # Hoja original y hoja extendida
        ws_src = sheet
        ws_out = workbook.add_worksheet('Cartera Extendida')

        def _norm(s):
            return (s or '').strip().upper()

        # === SOLO LÓGICA TIPO "REPORTE" (ELSE) ===
        drop_set = set(map(_norm, [
            'REF_EMPRESA',      # eliminar
            'REF_ALMACEN_ID',   # eliminar
            'REF_GRU_ID',       # eliminar
            'REF_DOCUMENTADO',
            'REF_INTERES',
            'REF_TASA_INTERES',
            'REF_VALOR_MORA',
            'REF_DIAS_MORA',
            'REF_GESTION_ID',
            'REF_GESTION_NOMBRE',
            'REF_ESTADO_ID',
            'REF_ESTADO_NOMBRE',
        ]))
        final_headers = [h for h in headers if _norm(h) not in drop_set]

        rename_map = {
            'FECHA_DATOS': 'Fecha de corte',
            'CUPO_CLIENTE': 'Cupo de cliente',
            'REF_CLI_TIPO_IDE': 'Código de tipo de identificación',
            'REF_CLI_IDENTIFICACION': 'Número de identificación',
            'REF_CLI_NOMBRE': 'Razón social',
            'REF_CLI_TELEFONO': 'Teléfono',
            'REF_CLI_CELULAR': 'Celular',
            'REF_CLI_MAIL': 'Correo electrónico',
            'REF_CLI_CALLE_PRINCIPAL': 'Calle principal',
            'REF_CLI_CALLE_SECUNDARIA': 'Calle secundaria',
            'REF_CLI_CIUDAD': 'Ciudad',
            'REF_COD_PAIS': 'Código país',
            'REF_COD_PROVINCIA': 'Código provincia',
            'REF_COD_CIUDAD': 'Código ciudad',
            'COD_PARROQUIA': 'Código parroquia',
            'REF_DOCUMENTO': 'Número',
            'REF_PLAZO': 'Días plazo',
            'REF_PERIODICIDAD': 'Periodicidad',
            'REF_TRANSACCION': 'Tipo de documento',
            'REF_CUOTA': 'Número de cuota',
            'NUM_TOTAL_CUOTA': 'Número total de cuotas',
            'REF_VALOR': 'Valor',
            'REF_CANCELADO': 'Valor cancelado',
            'REF_SALDO': 'Saldo',
            'SALDO_POR_VENCER': 'Saldo por vencer',
            'SALDO_VENCIDO': 'Saldo vencido',
            'EDAD': 'Edad',
            'TIPO': 'Tipo',
            'REF_FECHA_DOC': 'Fecha de documento',
            'REF_FECHA_EMI': 'Fecha de emisión',
            'ANO': 'Año',
            'Mes': 'Mes',
            'TERMINO_PAGO': 'Término de pago',
            'GARANTIA_CONTACTO': 'Garantía',
            'ULTIMA_CUOTA_PAGADA': 'Última cuota pagada',
            'REF_FECHA_VEN': 'Fecha de vencimiento',
            'REF_FECHA_CANCELA': 'Fecha de cancelación',
            'REF_ALMACEN_NOMBRE': 'Almacén',
            'REF_VEN_CEDULA': 'Número de identificación de vendedor',
            'REF_VEN_NOMBRE': 'Vendedor',
            'REF_CUE_ID': 'ID de la cuenta contable',
            'REF_CUE_NOMBRE': 'Cuenta contable',
            'REF_GRU_NOMBRE': 'Categoría de cliente',
        }

        visible_idx = [i for i, h in enumerate(headers) if h in final_headers]

        def _col_to_a1(col_idx):
            col = col_idx
            s = ""
            while col >= 0:
                s = chr(col % 26 + 65) + s
                col = col // 26 - 1
            return s

        ws_out.write(0, 0, 'Fecha de corte', formats['header_bg'])
        ws_out.write(0, 1, cutoff_date.strftime('%d-%m-%Y'), formats['date'])

        for out_c, src_c in enumerate(visible_idx):
            h = headers[src_c]
            # Ojo: aquí se mantiene la lógica original (uso de _norm en el get)
            title = rename_map.get(_norm(h), h)
            ws_out.write(1, out_c, title, formats['header_bg'])
            ws_out.set_column(out_c, out_c, max(len(title) + 2, 14))
        ws_out.set_column(0, len(visible_idx) - 1, 18)

        first_data_row = 2      # 0-based
        last_data_row = row - 1

        for r_src in range(first_data_row, last_data_row + 1):
            r_out = r_src
            for out_c, src_c in enumerate(visible_idx):
                a1_col = _col_to_a1(src_c)
                a1_row = r_src + 1  # A1 es 1-based
                ws_out.write_formula(r_out, out_c, f"=Cartera!{a1_col}{a1_row}", formats['border'])

        ws_src.hide()
        ws_out.activate()
        workbook.close()
        output.seek(0)
        self.file_data = base64.b64encode(output.read())
        self.file_name = f"cartera_reporte_{cutoff_date.strftime('%Y%m%d')}.xlsx"

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/?model={self._name}&id={self.id}&field=file_data&filename_field=file_name&download=true",
            'target': 'new',
        }
