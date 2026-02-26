# -*- coding: utf-8 -*-
import datetime as dt
from odoo.tests.common import SavepointCase, tagged
from odoo.exceptions import ValidationError

@tagged("post_install", "-at_install")
class TestPentaContractLogic(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Company = cls.env.ref("base.main_company")
        cls.Employee = cls.env["hr.employee"].create({
            "name": "Empleado Test Contratos",
            "company_id": cls.Company.id,
        })
        cls.structure_type = cls._ensure_structure_type()

        # Garantizar catálogos propios disponibles
        cls.IessOption = cls.env["hr.iess.option"]
        if not cls.IessOption.search([("option_type", "=", "patronal")], limit=1):
            cls.IessOption.create({
                "name": "12.15% IESS patronal",
                "option_type": "patronal",
                "percentage": 12.15,
            })
        if not cls.IessOption.search([("option_type", "=", "personal")], limit=1):
            cls.IessOption.create({
                "name": "9.45% IESS personal",
                "option_type": "personal",
                "percentage": 9.45,
            })
        if not cls.IessOption.search([("option_type", "=", "conyugal")], limit=1):
            cls.IessOption.create({
                "name": "No aplica",
                "option_type": "conyugal",
                "percentage": 0.0,
            })

        cls.AccountSection = cls.env["hr.account.section"]
        if not cls.AccountSection.search([], limit=1):
            cls.AccountSection.create({"name": "Gasto - Administrativo", "code": "GADM"})

    # --------------------------
    # Helpers
    # --------------------------
    @classmethod
    def _ensure_structure_type(cls):
        """Devuelve un structure_type válido para hr.contract (crea uno si falta)."""
        Contract = cls.env["hr.contract"]
        any_contract = Contract.search([], limit=1, order="id desc")
        if any_contract and any_contract.structure_type_id:
            return any_contract.structure_type_id

        Model = cls.env["ir.model"].sudo()
        model_name = None
        if Model.search([("model", "=", "hr.contract.structure.type")], limit=1):
            model_name = "hr.contract.structure.type"
        elif Model.search([("model", "=", "hr.payroll.structure.type")], limit=1):
            model_name = "hr.payroll.structure.type"
        if model_name:
            return cls.env[model_name].create({"name": "Structure Type Penta (Test)"})

        raise AssertionError(
            "No hay modelo de structure type. Instala hr_contract/hr_payroll o ajusta el test."
        )

    def _create_contract(self, name, start, end=None):
        Contract = self.env["hr.contract"].with_context(tracking_disable=True)
        return Contract.create({
            "name": name,
            "employee_id": self.Employee.id,
            "company_id": self.Company.id,
            "date_start": start,
            "date_end": end,
            "wage": 1000.0,
            "structure_type_id": self.structure_type.id,
        })

    # --------------------------
    # Tests
    # --------------------------
    def test_overlap_validation(self):
        c1 = self._create_contract("C1", dt.date(2023, 1, 1), dt.date(2023, 3, 31))
        with self.assertRaises(ValidationError):
            self._create_contract("C2", dt.date(2023, 2, 1), dt.date(2023, 4, 30))
        c3 = self._create_contract("C3", dt.date(2023, 4, 1), dt.date(2023, 6, 30))
        self.assertTrue(c1.id and c3.id)

    def test_total_time_in_service_merge(self):
        self._create_contract("A", dt.date(2020, 1, 1), dt.date(2020, 1, 31))
        self._create_contract("B", dt.date(2020, 1, 21), dt.date(2020, 2, 10))
        c3 = self._create_contract("C", dt.date(2020, 2, 12), dt.date(2020, 2, 20))
        c3.invalidate_recordset(["l10n_ec_ptb_years_in_service"])
        txt = c3.l10n_ec_ptb_years_in_service or ""
        self.assertIn("años", txt)
        self.assertNotEqual(txt.strip(), "0 años, 0 meses, 0 días")

    def test_previous_contracts_flags(self):
        c1 = self._create_contract("C1", dt.date(2022, 1, 1), dt.date(2022, 12, 31))
        self.assertFalse(c1.has_previous_contracts)
        self.assertFalse(c1.previous_contract_ids)

        c2 = self._create_contract("C2", dt.date(2023, 1, 1), dt.date(2023, 6, 30))
        c2.invalidate_recordset(["has_previous_contracts", "previous_contract_ids"])
        self.assertTrue(c2.has_previous_contracts)
        self.assertIn(c1, c2.previous_contract_ids)

    def test_assign_iess_and_account_section(self):
        iess_pat = self.IessOption.search([("option_type", "=", "patronal")], limit=1)
        iess_per = self.IessOption.search([("option_type", "=", "personal")], limit=1)
        iess_con = self.IessOption.search([("option_type", "=", "conyugal")], limit=1)
        acc_sec = self.AccountSection.search([], limit=1)

        c = self._create_contract("C-IESS", dt.date(2024, 1, 1))
        c.write({
            "iess_patronal_id": iess_pat.id,
            "iess_personal_id": iess_per.id,
            "iess_conyugal_id": iess_con.id,
            "account_section_id": acc_sec.id,
            "l10n_ec_ptb_thirteenth_fund_paid": "monthly",
            "l10n_ec_ptb_fourteenth_fund_paid": "accumulated",
            "l10n_ec_ptb_fourteenth_regime": "costa_fourteenth_salary",
            "l10n_ec_ptb_reserve_fund_periodicity": "monthly",
            "l10n_ec_ptb_reserve_fund_computation": "automatic",
            "relation_type": "empleado",
        })
        self.assertEqual(c.iess_patronal_id, iess_pat)
        self.assertEqual(c.iess_personal_id, iess_per)
        self.assertEqual(c.iess_conyugal_id, iess_con)
        self.assertEqual(c.account_section_id, acc_sec)
        self.assertTrue(c.l10n_ec_ptb_payment_profits)
