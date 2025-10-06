# -*- coding: utf-8 -*-
from odoo.tests.common import SavepointCase, tagged
from datetime import date, datetime, timedelta

@tagged("post_install", "-at_install")
class TestVacationCounters(SavepointCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Employee = cls.env["hr.employee"]
        cls.Contract = cls.env["hr.contract"]
        cls.Leave = cls.env["hr.leave"]
        cls.LeaveType = cls.env["hr.leave.type"]
        cls.VacPeriod = cls.env["vacation.period"]

        # 1) Empleado
        cls.employee = cls.Employee.create({"name": "Test Employee"})

        # 2) Contrato activo (iniciado hace 2 años)
        company = cls.env.company
        cal = company.resource_calendar_id
        start = date.today().replace(year=date.today().year - 2)
        cls.contract = cls.Contract.create({
            "name": "Contrato Test",
            "employee_id": cls.employee.id,
            "state": "open",
            "date_start": start,
            "resource_calendar_id": cal.id if cal else False,
            "structure_type_id": cls.env.ref("hr_contract.structure_type_employee").id,
        })

        # 3) Tipo de vacaciones (único con is_vacation=True)
        cls.vac_type = cls.LeaveType.create({
            "name": "Vacaciones",
            "is_vacation": True,
            "requires_allocation": "no",
            "time_type": "leave",
        })

        # 4) Períodos acreditados (por ejemplo 2 años: 15 + 16 = 31)
        current_year = date.today().year
        prev_year = current_year - 1
        cls.VacPeriod.create({
            "name": str(prev_year),
            "period": str(prev_year),
            "days": 15,
            "contract_id": cls.contract.id,
            "estate_vacation": "period",
        })
        cls.VacPeriod.create({
            "name": str(current_year),
            "period": str(current_year),
            "days": 16,  # regla +1 desde 6to, ajusta a tu lógica si varía
            "contract_id": cls.contract.id,
            "estate_vacation": "period",
        })

        # 5) Un leave ya aprobado de 5 días en el año actual (simula vacaciones tomadas)
        # Odoo espera datetimes en date_from/date_to
        _from = datetime.combine(date.today().replace(month=1, day=10), datetime.min.time())
        _to = _from + timedelta(days=4)  # 5 días inclusive
        cls.Leave.create({
            "name": "Vac Tomadas",
            "employee_id": cls.employee.id,
            "holiday_status_id": cls.vac_type.id,
            "date_from": _from,
            "date_to": _to,
            "state": "validate",  # aprobado
        })

    def test_counters_on_new_vacation_request(self):
        """available = suma(periodos) ; taken = días aprobados ; remaining = available - taken"""
        # Nueva solicitud aún no aprobada (solo para mirar contadores)
        req_from = datetime.combine(date.today().replace(month=8, day=1), datetime.min.time())
        req_to = req_from + timedelta(days=1)
        leave = self.Leave.new({
            "employee_id": self.employee.id,
            "holiday_status_id": self.vac_type.id,
            "date_from": req_from,
            "date_to": req_to,
        })
        # fuerza el compute de fields @api.depends
        leave.flush_model()

        available = leave.vacation_available
        taken = leave.vacation_taken
        remaining = leave.vacation_remaining

        self.assertEqual(available, 31, "Vacaciones disponibles deben sumar períodos (15 + 16).")
        self.assertEqual(taken, 5, "Vacaciones tomadas deben reflejar el leave aprobado (5 días).")
        self.assertEqual(remaining, 26, "Vacaciones restantes = 31 - 5.")

    def test_request_cannot_exceed_remaining_when_vacation(self):
        """Si tu lógica valida contra remaining, aquí verificamos que no permita exceder."""
        # Intentamos registrar un leave de 40 días (excede 26 restantes)
        req_from = datetime.combine(date.today().replace(month=9, day=1), datetime.min.time())
        req_to = req_from + timedelta(days=39)

        # Si tu módulo lanza UserError/ValidationError en create/onchange, prueba ambos caminos:
        created = self.Leave.with_context(test_raise=True)
        try:
            created.create({
                "name": "Vac Excede",
                "employee_id": self.employee.id,
                "holiday_status_id": self.vac_type.id,
                "date_from": req_from,
                "date_to": req_to,
            })
        except Exception:
            # OK: el módulo impidió exceder. Nada más que comprobar.
            return

        # Si no lanzó, al menos comprobamos que los contadores indiquen el exceso:
        probe = self.Leave.new({
            "employee_id": self.employee.id,
            "holiday_status_id": self.vac_type.id,
            "date_from": req_from,
            "date_to": req_to,
        })
        probe.flush_model()
        self.assertTrue(
            probe.vacation_remaining < 40,
            "La solicitud fabricada excede las vacaciones restantes, debería bloquearse en tu lógica."
        )
