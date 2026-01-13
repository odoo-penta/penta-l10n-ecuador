# -*- coding: utf-8 -*-
# l10n_ec_rrhh_penta – Contratos Ecuador
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from datetime import date, datetime

# Utilidad: validar solapamiento de [start, end] (end None = abierto)
def _ranges_overlap(a_start, a_end, b_start, b_end):
    a_end = a_end or date.max
    b_end = b_end or date.max
    return not (a_end < b_start or b_end < a_start)

class HrIessOption(models.Model):
    _name = "hr.iess.option"
    _description = "Afiliación IESS (parametrización)"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    # tipos: patronal, personal, conyugal, personal_assumed (por si luego)
    option_type = fields.Selection([
        ("patronal", "Patronal"),
        ("personal", "Personal"),
        ("conyugal", "Extensión conyugal"),
        ("personal_assumed", "Personal asumido"),
    ], required=True)
    percentage = fields.Float(string="Porcentaje (%)", digits=(6, 2))
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    notes = fields.Char()

    _sql_constraints = [
        ("name_type_uniq", "unique(name, option_type)",
         "Ya existe esta opción con el mismo tipo."),
    ]


class HrAccountSection(models.Model):
    _name = "hr.account.section"
    _description = "Sección contable para nómina"
    _order = "sequence, name"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", help="Código interno de la sección.")
    sequence = fields.Integer(string="Secuencia", default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("hr_account_section_name_uniq", "unique(name)", "El nombre de la sección debe ser único."),
    ]


class HrContract(models.Model):
    _inherit = "hr.contract"

    # ===== Campos solicitados =====
    l10n_ec_ptb_sectoral_code_iess = fields.Char(
        string="Código sectorial IESS",
        related="job_id.iess_sector_code",
        readonly=True, store=False
    )
    l10n_ec_ptb_code_mrl = fields.Char(
        string="Código MDT",
        help="Código asignado en el Ministerio de Trabajo."
    )
    # Tiempo de servicio TOTAL (todos los contratos del empleado, sin solapes)
    l10n_ec_ptb_years_in_service = fields.Char(
        compute="_compute_total_time_in_service",
        string="Tiempo Servicio Contrato",
        readonly=True,
        help="Tiempo total de servicio sumando todos los contratos del empleado (sin solapes)."
    )
    # Blobs y quincena
    l10n_ec_ptb_input_iess = fields.Binary(
        string="Documentos de entrada IESS",
        help="Adjunte documentos de entrada al IESS (comprimir si son varios)."
    )
    l10n_ec_ptb_output_iess = fields.Binary(
        string="Documentos de salida IESS",
        help="Adjunte documentos de salida del IESS (comprimir si son varios)."
    )
    l10n_ec_ptb_fortnight = fields.Monetary(string="Quincena")
    # Fondo de reserva: solo Mensual / Acumulado (sin 'Sin Fondo')
    l10n_ec_ptb_reserve_fund_periodicity = fields.Selection([
        ("monthly", "Mensual"),
        ("accumulated", "Acumulado"),
    ], default="monthly", required=True, string="Pago Fondo Reserva")
    # Cálculo: automático luego de 1 año (en acumulado) o forzar
    l10n_ec_ptb_reserve_fund_computation = fields.Selection([
        ("automatic", "Automático (luego de 1 año)"),
        ("always_force", "Forzar Pago"),
    ], default="automatic", required=True, string="Pago de fondos de reserva")
    # Décimos: Mensual / Acumulado / No definido
    l10n_ec_ptb_thirteenth_fund_paid = fields.Selection([
        ("monthly", "Mensual"),
        ("accumulated", "Acumulado"),
        ("undefined", "No definido"),
    ], string="Pago del décimo tercer sueldo")

    l10n_ec_ptb_fourteenth_fund_paid = fields.Selection([
        ("monthly", "Mensual"),
        ("accumulated", "Acumulado"),
        ("undefined", "No definido"),
    ], string="Pago del décimo cuarto sueldo")

    l10n_ec_ptb_fourteenth_regime = fields.Selection([
        ("sierra_fourteenth_salary", "Región Sierra"),
        ("costa_fourteenth_salary", "Región Costa"),
    ], string="Periodo de Pago")

    # Utilidades por relación con la empresa
    relation_type = fields.Selection([
        ("empleado", "Empleado (recibe)"),
        ("gerente", "Gerente (no recibe)"),
        ("socio", "Socio (no recibe)"),
        ("artesano", "Artesano (no recibe)"),
    ], default="empleado", string="Relación empresa")
    l10n_ec_ptb_payment_profits = fields.Boolean(
        string="Cobra utilidades",
        compute="_compute_payment_profits", store=True
    )

    # CRUD: IESS parametrizado
    iess_patronal_id = fields.Many2one(
        "hr.iess.option", string="IESS Patronal",
        domain="[('option_type', '=', 'patronal'), ('active','=',True)]"
    )
    iess_personal_id = fields.Many2one(
        "hr.iess.option", string="IESS Personal",
        domain="[('option_type', '=', 'personal'), ('active','=',True)]"
    )
    iess_conyugal_id = fields.Many2one(
        "hr.iess.option", string="Extensión conyugal",
        domain="[('option_type', '=', 'conyugal'), ('active','=',True)]"
    )

    # Sección contable
    account_section_id = fields.Many2one(
        "hr.account.section", string="Sección contable"
    )

    # Pestaña "Contratos anteriores"
    has_previous_contracts = fields.Boolean(
        compute="_compute_has_previous_contracts", store=False
    )
    previous_contract_ids = fields.Many2many(
        "hr.contract", compute="_compute_previous_contracts", store=False,
        string="Contratos anteriores"
    )

    analytic_distribution = fields.Json(
        string="Distribución Analítica",
        default={},
        help="Define la distribución de costos en diferentes cuentas analíticas."
    ) 
    analytic_precision = fields.Integer(
        string="Precisión Analítica",
        default=2,
        help="Cantidad de decimales que se utilizarán para los porcentajes en la distribución analítica."
    )
    reason_end = fields.Many2one('hr.departure.reason', string="Motivo salida legal")
    code_iess = fields.Char(string="Código novedad IESS", help="Aviso de entrada")
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        employee_id = self.env.context.get('default_employee_id', False)
        if not employee_id:
            return res
        employee = self.env['hr.employee'].browse(employee_id)
        if not employee.exists():
            return res
        if not res.get('department_id') and employee.department_id:
            res['department_id'] = employee.department_id.id
        if not res.get('job_id') and employee.job_id:
            res['job_id'] = employee.job_id.id
        return res

    # ====== Cómputos ======
    @api.depends("relation_type")
    def _compute_payment_profits(self):
        for rec in self:
            rec.l10n_ec_ptb_payment_profits = (rec.relation_type == "empleado")

    @api.depends("employee_id", "date_start", "date_end", "active")
    def _compute_has_previous_contracts(self):
        for rec in self:
            if not rec.employee_id:
                rec.has_previous_contracts = False
                continue
            others = self.search([
                ("employee_id", "=", rec.employee_id.id),
                ("id", "!=", rec.id),
            ])
            rec.has_previous_contracts = bool(others)

    @api.depends("employee_id", "date_start", "date_end", "active")
    def _compute_previous_contracts(self):
        for rec in self:
            if not rec.employee_id:
                rec.previous_contract_ids = False
                continue
            rec.previous_contract_ids = self.search([
                ("employee_id", "=", rec.employee_id.id),
                ("id", "!=", rec.id),
            ])

    @api.depends("employee_id", "date_start", "date_end", "active")
    def _compute_total_time_in_service(self):
        """Suma períodos de TODOS los contratos del empleado, unificando solapes."""
        for rec in self:
            emp = rec.employee_id
            if not emp:
                rec.l10n_ec_ptb_years_in_service = "0 años, 0 meses, 0 días"
                continue
            # Traer todos los contratos del empleado (activos o archivados)
            contracts = self.search([("employee_id", "=", emp.id)])
            # construir lista de (start, end) fechas
            ranges = []
            for c in contracts:
                if not c.date_start:
                    continue
                start = c.date_start
                end = c.date_end or date.today()
                if end < start:
                    start, end = end, start
                ranges.append((start, end))

            # Unificar rangos solapados
            ranges.sort(key=lambda r: r[0])
            merged = []
            for r in ranges:
                if not merged:
                    merged.append(list(r))
                else:
                    last = merged[-1]
                    if r[0] <= last[1]:
                        # extiende
                        if r[1] > last[1]:
                            last[1] = r[1]
                    else:
                        merged.append(list(r))

            # Sumar duración total
            total_days = 0
            for (s, e) in merged:
                total_days += (e - s).days + 1  # inclusivo
            # Convertir a años/meses/días aprox.
            # Para precisión exacta calendario, podríamos iterar mes a mes;
            # aquí usamos relativedelta desde 0
            base = date(2000, 1, 1)
            end = base + relativedelta(days=total_days)
            rd = relativedelta(end, base)
            rec.l10n_ec_ptb_years_in_service = f"{rd.years} años, {rd.months} meses, {rd.days} días"

    # ====== Validación de solapamiento ======
    @api.constrains("employee_id", "date_start", "date_end", "active")
    def _check_overlap_contracts(self):
        for rec in self:
            if not rec.employee_id or not rec.date_start:
                continue
            others = self.search([
                ("employee_id", "=", rec.employee_id.id),
                ("id", "!=", rec.id),
            ])
            for o in others:
                if _ranges_overlap(rec.date_start, rec.date_end, o.date_start, o.date_end):
                    raise ValidationError(_(
                        "Solapamiento de contratos para %s entre %s–%s y %s–%s."
                    ) % (
                        rec.employee_id.display_name,
                        rec.date_start or "-", rec.date_end or "abierto",
                        o.date_start or "-", o.date_end or "abierto"
                    ))
                
    @api.model
    def _create_accounting_entries(self):
        """ Crea asientos contables asegurando la correcta distribución analítica por porcentaje. """
        for contract in self:
            total_amount = contract.wage  # Sueldo a distribuir
            analytic_distribution = contract.analytic_distribution

            if not analytic_distribution:
                continue  # Si no hay distribución analítica, no hacemos nada

            move_lines = []
            for analytic_account_id, percentage in analytic_distribution.items():
                move_lines.append({
                    'account_id': contract.salary_account_id.id,
                    'partner_id': contract.employee_id.address_home_id.id,
                    'debit': (total_amount * percentage) / 100.0,  # Aplica porcentaje
                    'credit': 0.0,
                    'analytic_distribution': {analytic_account_id: percentage},  # Aplica distribución analítica
                })

            self.env['account.move.line'].create(move_lines)
                    
    def action_open_add_vacation_wizard(self):
        """Abre el asistente 'Agregar vacaciones' con el contrato en contexto."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Ajustar vacaciones",
            "res_model": "l10n_ec.ptb.add.vacation.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("l10n_ec_rrhh_penta.view_l10n_ec_ptb_add_vacation_wizard_form").id,
            "target": "new",
            "context": {
                "default_contract_id": self.id,
            },
        }

class HrContractType(models.Model):
    _inherit = "hr.contract.type"

    active = fields.Boolean(default=True)
