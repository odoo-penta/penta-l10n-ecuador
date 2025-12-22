# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError

@tagged("post_install", "-at_install")
class TestPaymentMode(TransactionCase):

    def test_default_data_exists(self):
        # precargados
        transfer = self.env.ref("l10n_ec_rrhh_penta.hr_payment_mode_transfer")
        check = self.env.ref("l10n_ec_rrhh_penta.hr_payment_mode_check")
        self.assertEqual(transfer.name, "Transferencia")
        self.assertEqual(check.name, "Cheque")

    def test_crud_payment_mode(self):
        Mode = self.env["hr.payment.mode"]
        # Create
        pm = Mode.create({"name": "Depósito", "sequence": 15})
        self.assertTrue(pm.id)
        self.assertTrue(pm.active)

        # Write
        pm.write({"name": "Depósito bancario", "active": False})
        self.assertEqual(pm.name, "Depósito bancario")
        self.assertFalse(pm.active)

        # Unique name
        with self.assertRaises(ValidationError):
            Mode.create({"name": "Transferencia"})

    def test_employee_link(self):
        # Asignar modo de pago al empleado y leer
        employee = self.env["hr.employee"].create({"name": "Empleado ModoPago"})
        transfer = self.env.ref("l10n_ec_rrhh_penta.hr_payment_mode_transfer")
        employee.payment_mode_id = transfer.id
        self.assertEqual(employee.payment_mode_id, transfer)
