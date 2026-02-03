# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from datetime import date

def ec_validate_cedula(ced):
    """
    Valida cédula ecuatoriana (10 dígitos):
    - 01..24 provincia
    - 3er dígito < 6
    - checksum módulo 10 coef [2,1,2,1,2,1,2,1,2]
    """
    if not ced or len(ced) != 10 or not ced.isdigit():
        return False
    prov = int(ced[0:2])
    if prov < 1 or prov > 24:
        return False
    if int(ced[2]) >= 6:
        return False
    coef = [2,1,2,1,2,1,2,1,2]
    total = 0
    for i in range(9):
        prod = int(ced[i]) * coef[i]
        if prod >= 10:
            prod -= 9
        total += prod
    ver = (10 - (total % 10)) % 10
    return ver == int(ced[9])

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    identification_id = fields.Char(string='Identification No', required=True, groups="hr.group_hr_user", tracking=True)
    # 1) Nivel de educación configurable (ocultamos certificate nativo en la vista)
    education_level_id = fields.Many2one(
        "hr.education.level", string="Nivel de Educación"
    )
    # 2) Discapacidad
    disability_type_id = fields.Many2one(
        "hr.disability.type", string="Tipo de discapacidad"
    )
    blood_type = fields.Selection([
        ("O+", "O+"), ("O-", "O-"),
        ("A+", "A+"), ("A-", "A-"),
        ("B+", "B+"), ("B-", "B-"),
        ("AB+", "AB+"), ("AB-", "AB-"),
    ], string="Tipo de sangre")
    payment_mode_id = fields.Many2one("hr.payment.mode", string="Modo de pago")
    children = fields.Integer(
        string="Cargas familiares para utilidades",
        compute="_compute_children_from_dependents",
        store=True, readonly=True,
    )
    cupo = fields.Float(string="Cupo", digits=(16, 2), help="Cupo asignado al empleado.")
    disability_percentage = fields.Float(
        string="Porcentaje de discapacidad (%)",
        help="Ingrese un valor entre 0 y 100.",
        digits=(16, 2),   # 2 decimales; 
        default=0.0,
    )
    has_subrogation = fields.Boolean(string="Tiene subrogación")
    # Campos condicionados por is_subrogated del tipo elegido:
    subrogated_name = fields.Char(string="Nombre de subrogado")
    subrogated_certificate = fields.Char(string="Certificado de sustituto directo")
    subrogated_identification_type = fields.Selection([
        ("cedula", "Cédula"),
        ("passport", "Pasaporte"),
    ], string="Tipo de identificación del subrogado")
    subrogated_identification = fields.Char(string="Identificación del subrogado")
    # Empleado sustituto
    is_substitute = fields.Boolean(string="¿Es substituto?")
    substitute_name = fields.Char(string="Nombre del dependiente")
    substitute_identification = fields.Char(string="Identificación del sustituto")
    type_substitute = fields.Many2one('hr.substitute.type', string="Tipo de sustituto")
    relationship_substitute = fields.Many2one('hr.substitute.relationship', string="Parentesco")
    # 3) Estado civil: reordenar y traducir “Unión de hecho”
    marital = fields.Selection(
        selection="_get_marital_status_selection",
        string="Estado civil",
        groups="hr.group_hr_user",
        default="single",
        required=True,
        tracking=True,
    )
    has_catastrophic_disease = fields.Boolean(
        string="El empleado tiene alguna enfermedad catastrófica",
        help="Marque si el empleado posee una enfermedad catastrófica."
    )
    catastrophic_certificate_date = fields.Date(
        string="Fecha del certificado"
    )
    catastrophic_certificate_number = fields.Char(
        string="Número del certificado",
        size=64
    )
    catastrophic_description = fields.Text(
        string="Descripción de la enfermedad catastrófica"
    )
    # Contrato "actual" usado para el cálculo/ajuste
    current_contract_id = fields.Many2one(
        "hr.contract", compute="_compute_current_contract", store=False, string="Contrato actual"
    )
    # Totales agregados (solo lectura)
    vac_total_entitled = fields.Float(
        related="current_contract_id.vac_total_entitled",
        string="Acreditadas"
    )
    vac_total_taken = fields.Float(
        related="current_contract_id.vac_total_taken",
        string="Tomadas"
    )
    vac_total_available = fields.Float(
        related="current_contract_id.vac_total_available",
        string="Disponibles"
    )

    @api.constrains("disability_percentage")
    def _check_disability_percentage(self):
        for rec in self:
            if rec.disability_percentage is not False:
                if rec.disability_percentage < 0.0 or rec.disability_percentage > 100.0:
                    raise ValidationError(
                        _("El porcentaje de discapacidad debe estar entre 0 y 100.")
                    )
    
    @api.depends(
        "family_dependent_ids",
        "family_dependent_ids.relationship",
        "family_dependent_ids.is_child",
        "family_dependent_ids.birthdate",
    )
    def _compute_children_from_dependents(self):
        for emp in self:
            count = 0
            for dep in emp.family_dependent_ids:
                # Verificar hijo menor de 18, cónyuge o hijo con discapacidad
                if dep.relationship == "spouse":
                    count += 1
                elif dep.relationship == "children":
                    if dep.disability or (dep.birthdate and (fields.Date.today() - dep.birthdate).days / 365 < 18):
                        count += 1
            emp.children = count

    def action_open_contracts(self):
        """Abre los contratos del empleado en una vista de lista/form."""
        self.ensure_one()
        action = self.env.ref("hr_contract.hr_contract_action").read()[0]
        # Filtra por empleado actual
        action["domain"] = [("employee_id", "=", self.id)]
        # Opcional: contexto por defecto
        action.setdefault("context", {})
        action["context"].update({
            "default_employee_id": self.id,
        })
        return action

    @api.depends("contract_id", "contract_ids.state", "contract_ids.date_start", "contract_ids.date_end")
    def _compute_current_contract(self):
        today = date.today()
        for emp in self:
            Contract = emp.env["hr.contract"].sudo()
            contract = Contract.search([
                ("employee_id", "=", emp.id),
                "|", ("date_end", "=", False), ("date_end", ">=", today),
            ], order="date_start desc", limit=1)
            emp.current_contract_id = contract

    def _get_marital_status_selection(self):
        # Orden y etiquetas pedidas: Soltero(a), Casado(a), Divorciado(a), Viudo(a), Unión de hecho.
        return [
            ("single", _("Soltero(a)")),
            ("married", _("Casado(a)")),
            ("divorced", _("Divorciado(a)")),
            ("widower", _("Viudo(a)")),
            ("cohabitant", _("Unión de hecho")),
        ]

    # 4) Cargas familiares (conteo para impuesto a la renta)
    family_dependent_ids = fields.One2many(
        "l10n_ec.ptb.family.dependents", "employee_id", string="Cargas familiares"
    )
    num_family_dependent_tax = fields.Integer(
        string="Cargas familiares para impuesto a la renta",
        compute="_compute_num_family_dependent_tax", store=False
    )

    @api.depends("family_dependent_ids", "family_dependent_ids.use_for_income_tax")
    def _compute_num_family_dependent_tax(self):
        for emp in self:
            emp.num_family_dependent_tax = sum(
                1 for dep in emp.family_dependent_ids if dep.use_for_income_tax
            )
                    
    @api.constrains("identification_id")
    def _check_identification_unique_and_valid(self):
        for emp in self:
            if emp.identification_id:
                if not ec_validate_cedula(emp.identification_id):
                    # Otros tipos (pasaporte), 
                    raise ValidationError("La cédula del empleado no es válida.")
                clash = self.search_count([
                    ("id", "!=", emp.id),
                    ("identification_id", "=", emp.identification_id),
                ])
                if clash:
                    raise ValidationError("Ya existe un empleado con esta cédula (incluye archivados).")
