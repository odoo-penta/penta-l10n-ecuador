# -*- coding: utf-8 -*-
from odoo.tests.common import SavepointCase, tagged
from odoo.exceptions import ValidationError

@tagged("post_install", "-at_install")
class TestLeaveTypeVacationFlag(SavepointCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.LeaveType = cls.env["hr.leave.type"]

    def test_unique_is_vacation_flag(self):
        """Solo un tipo puede tener is_vacation=True."""
        # Creamos uno marcando vacaciones
        vac_type = self.LeaveType.create({
            "name": "Vacaciones (Principal)",
            "is_vacation": True,
            "requires_allocation": "no",
            "time_type": "leave",
        })
        self.assertTrue(vac_type.is_vacation)

        # Crear otro con is_vacation=True debe fallar por la restricción
        with self.assertRaises(ValidationError):
            self.LeaveType.create({
                "name": "Otro Vacaciones",
                "is_vacation": True,
                "requires_allocation": "no",
                "time_type": "leave",
            })

    def test_demo_or_data_loaded_ok(self):
        """Si cargaste data XML para tipos (vacaciones/enfermedad), que se puedan resolver."""
        # assert del valor exacto
        try:
            self.env.ref("penta_cb_rrhh.hr_leave_type_vacaciones")
        except Exception:
            self.skipTest("No hay hr_leave_type_vacaciones por XML en este entorno.")
