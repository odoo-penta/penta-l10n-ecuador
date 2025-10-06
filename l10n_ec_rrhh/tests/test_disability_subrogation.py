# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError

@tagged("post_install", "-at_install")
class TestDisabilitySubrogation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.emp = self.env["hr.employee"].create({"name": "Empleado Subr"})
        self.dt_sub = self.env["hr.disability.type"].create({"name": "Intelectual", "is_subrogated": True})
        self.dt_nosub = self.env["hr.disability.type"].create({"name": "Física", "is_subrogated": False})

    def test_requires_subrogation_fields(self):
        self.emp.disability_type_id = self.dt_sub
        with self.assertRaises(ValidationError):
            self.emp._check_subrogation_fields()

        # completa campos y debe pasar
        self.emp.write({
            "subrogated_name": "Juan Subrogado",
            "subrogated_identification_type": "cedula",
            "subrogated_identification": "1710034065",  # cédula válida
        })
        self.emp._check_subrogation_fields()  # no debe lanzar

    def test_invalid_cedula(self):
        self.emp.write({
            "disability_type_id": self.dt_sub,
            "subrogated_name": "Juan Subrogado",
            "subrogated_identification_type": "cedula",
            "subrogated_identification": "1234567890",  # inválida
        })
        with self.assertRaises(ValidationError):
            self.emp._check_subrogation_fields()

    def test_no_requirements_if_not_subrogated(self):
        self.emp.disability_type_id = self.dt_nosub
        self.emp._check_subrogation_fields()  # no debe lanzar aunque campos estén vacíos
