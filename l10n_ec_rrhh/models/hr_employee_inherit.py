# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

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

    # 1) Nivel de educación configurable (ocultamos certificate nativo en la vista)
    education_level_id = fields.Many2one(
        "hr.education.level", string="Nivel de Educación"
    )

    # 2) Discapacidad
    disability_type_id = fields.Many2one(
        "hr.disability.type", string="Tipo de discapacidad"
    )
    has_subrogation = fields.Boolean(string="Tiene subrogación", compute="_compute_has_subrogation", store=False)
    
    blood_type = fields.Selection([
        ("O+", "O+"), ("O-", "O-"),
        ("A+", "A+"), ("A-", "A-"),
        ("B+", "B+"), ("B-", "B-"),
        ("AB+", "AB+"), ("AB-", "AB-"),
    ], string="Tipo de sangre")

    payment_mode_id = fields.Many2one("hr.payment.mode", string="Modo de pago")
    
    children = fields.Integer(
        string="Número de hijos dependientes",
        compute="_compute_children_from_dependents",
        store=True, readonly=True,
    )
    
    @api.depends("family_dependent_ids", "family_dependent_ids.relationship", "family_dependent_ids.is_child")
    def _compute_children_from_dependents(self):
        for emp in self:
            emp.children = sum(
                1 for dep in emp.family_dependent_ids
                if dep.relationship == "children" or dep.is_child
            )

    @api.depends("disability_type_id", "disability_type_id.is_subrogated")
    def _compute_has_subrogation(self):
        for rec in self:
            rec.has_subrogation = bool(rec.disability_type_id and rec.disability_type_id.is_subrogated)
    # Campos condicionados por is_subrogated del tipo elegido:
    subrogated_name = fields.Char(string="Nombre de subrogado")
    subrogated_certificate = fields.Char(string="Certificado de sustituto directo")
    subrogated_identification_type = fields.Selection([
        ("cedula", "Cédula"),
        ("ruc", "RUC"),
        ("passport", "Pasaporte"),
    ], string="Tipo de identificación del subrogado")
    subrogated_identification = fields.Char(string="Identificación del subrogado")

    # 3) Estado civil: reordenar y traducir “Unión de hecho”
    marital = fields.Selection(
        selection="_get_marital_status_selection",
        string="Estado civil",
        groups="hr.group_hr_user",
        default="single",
        required=True,
        tracking=True,
    )

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

    # Validaciones de subrogación
    @api.constrains("disability_type_id", "subrogated_identification_type", "subrogated_identification")
    def _check_subrogation_fields(self):
        for emp in self:
            if emp.disability_type_id and emp.disability_type_id.is_subrogated:
                # Deben completarse los campos claves
                missing = []
                if not emp.subrogated_name:
                    missing.append("Nombre de subrogado")
                if not emp.subrogated_identification_type:
                    missing.append("Tipo de identificación de subrogado")
                if not emp.subrogated_identification:
                    missing.append("Identificación de subrogado")
                if missing:
                    raise ValidationError(
                        _("Debe completar los siguientes campos por subrogación: %s") % ", ".join(missing)
                    )
                # Validador de cédula
                if emp.subrogated_identification_type == "cedula":
                    if not ec_validate_cedula(emp.subrogated_identification):
                        raise ValidationError(_("La cédula del subrogado no es válida."))
                    
    @api.constrains("identification_id")
    def _check_identification_unique_and_valid(self):
        for emp in self:
            if emp.identification_id:
                if not ec_validate_cedula(emp.identification_id):
                    # Si manejas otros tipos (pasaporte), quita esta validación estricta
                    raise ValidationError("La cédula del empleado no es válida.")
                clash = self.search_count([
                    ("id", "!=", emp.id),
                    ("identification_id", "=", emp.identification_id),
                ])
                if clash:
                    raise ValidationError("Ya existe un empleado con esta cédula (incluye archivados).")
