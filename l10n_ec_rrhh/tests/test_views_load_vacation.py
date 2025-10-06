# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestVacationViews(TransactionCase):
    def test_views_compile(self):
        View = self.env["ir.ui.view"]
        View.clear_caches()
        # Form inherit que agrega los 3 campos
        self.env.ref("l10n_ec_rrhh.view_hr_leave_form_inherit_vac_kpis")
        # Form inherit de leave.type para is_vacation
        self.env.ref("l10n_ec_rrhh.view_hr_leave_type_form_inherit_vacation_flag")
