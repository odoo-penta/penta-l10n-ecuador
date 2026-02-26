# -*- coding: utf-8 -*-
from odoo import fields, models

class HrPayslipInputType(models.Model):
    _inherit = "hr.payslip.input.type"

    # opcional; úsalo para enrutar a sección
    penta_category = fields.Selection(
        [
            ("income", "INGRESO"),
            ("deduction", "DESCUENTO"),
        ],
        string="Categoría (Penta)",
        help="Clasificación para importación masiva: INGRESO o DESCUENTO.",
    )

class HrPayslipInput(models.Model):
    _inherit = "hr.payslip.input"

    penta_section = fields.Selection(
        [
            ("income_fixed", "INGRESOS ADICIONALES FIJOS"),
            ("deduction_fixed", "DESCUENTOS ADICIONALES FIJOS"),
        ],
        string="Sección (Penta)",
        help="Marcador de sección para reportes locales.",
    )
