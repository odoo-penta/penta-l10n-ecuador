# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = "res.partner"

    # ---------------------------
    # 1) Leer chips del account.report
    # ---------------------------
    def _followup__read_report_chips(self):
        """Lee los filtros configurados en account_reports.followup_report (modelo account.report).
        No usa métodos privados: solo campos reales si existen."""
        chips = {}
        report = self.env.ref('account_reports.followup_report', raise_if_not_found=False)
        if not report:
            return chips

        f = report._fields  # introspección segura

        # Tipos de cuenta (both | payable | receivable | disabled)
        if 'filter_account_type' in f:
            chips['filter_account_type'] = report.filter_account_type or 'both'

        # Diarios (algunas bases usan 'journal_ids', otras 'journals')
        if 'journal_ids' in f:
            chips['journal_ids'] = report.journal_ids.ids
        elif 'journals' in f:
            chips['journal_ids'] = report.journals.ids  # normalizamos a 'journal_ids'

        # Mostrar solo no conciliados (si el reporte guarda la preferencia)
        for name in ('show_unreconciled_only', 'filter_unreconciled', 'unreconciled_only'):
            if name in f:
                chips['show_unreconciled_only'] = bool(report[name])
                break

        # Fecha "Al ..." (si el reporte guarda un tope)
        # Muchas veces el report no guarda nada => dejamos vacío.
        if 'date_to' in f and report.date_to:
            chips['date'] = {'date_to': report.date_to}
        elif 'date' in f and report.date and isinstance(report.date, dict) and report.date.get('date_to'):
            chips['date'] = {'date_to': report.date['date_to']}

        return chips

    # ---------------------------
    # 2) Armar options finales combinando chips + partner/followup_line
    # ---------------------------
    def _followup__get_report_options(self):
        """Combina los chips de account.report con el envoltorio del modelo account.followup.report."""
        self.ensure_one()
        chips = self._followup__read_report_chips()
        # usa el modelo del seguimiento para inyectar partner_id/followup_line/context
        options = self.env['account.followup.report']._get_followup_report_options(self, chips or {})
        # por si no vino 'partner_ids'
        options.setdefault('partner_ids', [self.commercial_partner_id.id])
        options.setdefault('date', {})
        return options

    # ---------------------------
    # 3) Dominio a partir de esas options (igual que antes)
    # ---------------------------
    def _followup__domain_from_options(self, options):
        domain = [
            ('reconciled', '=', False),
            ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable')),
            ('parent_state', '=', 'posted'),
            ('partner_id', 'in', self.ids),
            ('company_id', 'child_of', self.env.company.id),
        ]
        ftype = (options.get('filter_account_type') or '').strip()
        if ftype == 'payable':
            domain[1] = ('account_id.account_type', '=', 'liability_payable')
        elif ftype == 'receivable':
            domain[1] = ('account_id.account_type', '=', 'asset_receivable')
        elif ftype == 'both':
            domain[1] = ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable'))

        journal_ids = options.get('journal_ids') or []
        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))

        if options.get('show_unreconciled_only') is False:
            domain = [d for d in domain if d[0] != 'reconciled']

        date_to = (options.get('date') or {}).get('date_to')
        if date_to:
            domain.append(('date', '<=', date_to))
        return domain

    # ---------------------------
    # 4) Fecha de corte
    # ---------------------------
    def _followup__today_from_options(self, options):
        date_to = (options.get('date') or {}).get('date_to')
        return fields.Date.from_string(date_to) if date_to else fields.Date.context_today(self)

    # ---------------------------
    # 5) Totales
    # ---------------------------
    def _get_followup_totals(self):
        """
        Cartera = suma con signo de residuales.
        Overdue bruto = líneas vencidas o pagos; mostrado = max(bruto, 0).
        Corriente = Cartera - Overdue mostrado.
        """
        self.ensure_one()
        options = self._followup__get_report_options()
        domain = self._followup__domain_from_options(options)

        allowed_company_ids = self.env.context.get('allowed_company_ids', self.env.company.ids)
        if isinstance(allowed_company_ids, int):
            allowed_company_ids = [allowed_company_ids]

        aml = self.env['account.move.line'].search(domain).filtered(
            lambda l: l.company_id.id in allowed_company_ids
        )
        today = self._followup__today_from_options(options)

        total_all = 0.0
        total_issued = 0.0
        for l in aml:
            amt = l.amount_residual_currency if l.currency_id else l.amount_residual
            total_all += (amt or 0.0)
            maturity_or_date = l.date_maturity or l.date
            is_overdue = bool(maturity_or_date and today > maturity_or_date)
            is_payment = bool(l.payment_id)
            if is_overdue or is_payment:
                total_issued += (amt or 0.0)

        overdue_shown = total_issued if total_issued > 0 else 0.0
        current = total_all - overdue_shown
        return {
            'total_overdue': overdue_shown,
            'total_due': current,
            'total_importe': total_all,
        }