# -*- coding: utf-8 -*-
#################################################################################
# Author      : PentaLab (<https://pentalab.tech>)
# Copyright(c): 2025
# All Rights Reserved.
#
# This module is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################
{
    "name": "Penta Localización RRHH",
    "version": "18.0.1.0.0",
    "author": "PentaLab",
    "website": "",
    "license": "LGPL-3",
    "summary": "Adaptaciones RRHH: Educación parametrizable, Discapacidad con subrogación, Cargas familiares.",
    "depends": ["hr","hr_payroll","hr_work_entry_contract_enterprise"],
    "data": [
        "security/ir.model.access.csv",
        "data/education_level_data.xml",
        "data/disability_type_data.xml",
        "data/contract_type_data.xml",
        "data/iess_option_data.xml",
        "data/account_section_data.xml",
        "data/payment_mode_data.xml",
        "data/hr_leave_type_data.xml",
        "data/benefit_config_data.xml",
        "views/config_views.xml",
        "views/family_dependent_views.xml",
        "views/hr_employee_views.xml",
        "views/hr_contract_views.xml",
        "views/config_hr_contract_params_views.xml",
        "views/hr_work_location_views.xml",
        "views/hr_leave_type_views.xml",
        "views/hr_leave_views.xml",
        "views/hr_contract_vacation_views.xml",
        "views/benefits_menus.xml",
        "views/benefit_config_views.xml",
    ],
    "installable": True,
    "application": False,
    "images": ["static/description/icon.svg", "static/description/banner.svg"],
    "demo": [],
    "test": [],
}
