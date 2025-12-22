# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
from datetime import date

@tagged("post_install", "-at_install")
class TestFamilyDependents(TransactionCase):
    def setUp(self):
        super().setUp()
        self.emp = self.env["hr.employee"].create({"name": "Empleado Familia"})

    def _dep(self, **vals):
        data = {
            "employee_id": self.emp.id,
            "name": "Dep",
            "birthdate": date(2010, 1, 1),
            "relationship": "children",
        }
        data.update(vals)
        return self.env["l10n_ec.ptb.family.dependents"].create(data)

    def test_unique_spouse(self):
        self._dep(name="Pareja A", relationship="spouse")
        with self.assertRaises(ValidationError):
            self._dep(name="Pareja B", relationship="spouse")

    def test_tax_counter(self):
        self._dep(name="Hijo 1", relationship="children", use_for_income_tax=True)
        self._dep(name="Hijo 2", relationship="children", use_for_income_tax=False)
        self._dep(name="Padre", relationship="parents", use_for_income_tax=True)
        self.emp.invalidate_recordset(fnames=["family_dependent_ids"])
        self.assertEqual(self.emp.num_family_dependent_tax, 2)
