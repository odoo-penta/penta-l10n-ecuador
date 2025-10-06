# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestViewsLoad(TransactionCase):

    def test_views_and_actions_compile(self):
        View = self.env["ir.ui.view"]
        View.clear_caches()

        # --- Education Level CRUD
        self.env.ref("l10n_ec_rrhh.view_hr_education_level_tree")
        self.env.ref("l10n_ec_rrhh.view_hr_education_level_form")
        self.env.ref("l10n_ec_rrhh.action_hr_education_level")
        self.env.ref("l10n_ec_rrhh.menu_hr_education_level")

        # --- Disability Type CRUD
        self.env.ref("l10n_ec_rrhh.view_hr_disability_type_tree")
        self.env.ref("l10n_ec_rrhh.view_hr_disability_type_form")
        self.env.ref("l10n_ec_rrhh.action_hr_disability_type")
        self.env.ref("l10n_ec_rrhh.menu_hr_disability_type")

        # --- Payment Mode CRUD (nuevo)
        self.env.ref("l10n_ec_rrhh.view_hr_payment_mode_tree")
        self.env.ref("l10n_ec_rrhh.view_hr_payment_mode_form")
        self.env.ref("l10n_ec_rrhh.action_hr_payment_mode")
        self.env.ref("l10n_ec_rrhh.menu_hr_payment_mode")

        # --- Family dependents (lista + form + acción)
        self.env.ref("l10n_ec_rrhh.view_l10_ec_ptb_family_dependents_tree")
        self.env.ref("l10n_ec_rrhh.view_l10_ec_ptb_family_dependents_form")
        self.env.ref("l10n_ec_rrhh.action_l10_ec_ptb_family_dependents")

        # --- Employee form inherits
        self.env.ref("l10n_ec_rrhh.view_employee_form_inherit_penta_cb_rrhh_education")
        self.env.ref("l10n_ec_rrhh.view_employee_form_inherit_penta_cb_rrhh_disability")
        self.env.ref("l10n_ec_rrhh.view_employee_form_inherit_penta_cb_rrhh_family")
