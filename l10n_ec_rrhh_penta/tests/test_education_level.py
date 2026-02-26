# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestEducationLevel(TransactionCase):
    def test_create_education_level(self):
        lvl = self.env["hr.education.level"].create({"name": "Bachillerato", "code": "BACH"})
        self.assertTrue(lvl.id)
        emp = self.env["hr.employee"].create({"name": "Empleado Demo", "education_level_id": lvl.id})
        self.assertEqual(emp.education_level_id, lvl)
