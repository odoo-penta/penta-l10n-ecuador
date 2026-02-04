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
    "summary": "Adaptaciones RRHH: Educación parametrizable, Discapacidad con subrogación, Cargas familiares.",
    "description": """
        Adaptaciones RRHH: Educación parametrizable, Discapacidad con subrogación, Cargas familiares.
    """,
    'author': 'PentaLab',
    'maintainer': 'PentaLab',
    'contributors': ['AntonyPineda <vini16.av@gmail.com>'],
    'website': 'https://pentalab.tech/',
    "license": "LGPL-3",
    'category': 'Human Resources/Employees',
    "version": "18.0.9.2.4",
    "depends": [
        'analytic',
        'hr_contract',
        'hr_payroll_account',
        'hr_payroll_holidays',
    ],
    "data": [
        "data/education_level_data.xml",
        "data/disability_type_data.xml",
        "data/contract_type_data.xml",
        "data/iess_option_data.xml",
        "data/account_section_data.xml",
        "data/payment_mode_data.xml",
        "data/hr_leave_type_data.xml",
        "data/benefit_config_data.xml",
        'data/resource_calendar_data.xml',
        "data/hr_payroll_structure_types_data.xml",
        "data/hr_payroll_structures_data.xml",
        "data/hr_salary_rule_category_data.xml",
        "data/hr_payslip_input_type_data.xml",
        "data/hr_salary_rule_data.xml",
        "data/ir_cron.xml",
        
        "security/ir.model.access.csv",
        
        'report/report_payslip_templates.xml',
        'report/payslip_report.xml',
        
        "views/config_views.xml",
        "views/family_dependent_views.xml",
        "views/hr_employee_views.xml",
        "views/config_hr_contract_params_views.xml",
        "views/hr_work_location_views.xml",
        "views/hr_leave_type_views.xml",
        "views/hr_leave_views.xml",
        "views/vacation_wizard_views.xml",
        "views/hr_contract_vacation_views.xml",
        "views/benefits_menus.xml",
        "views/benefit_config_views.xml",
        "views/hr_contract_views.xml",
        "views/hr_job_views.xml",
        "views/hr_employee_vacations_dashboard.xml",
        "views/hr_salary_rule_views.xml",
        "views/hr_account_section_views.xml",
        "views/vacations_bulk_adjust_views.xml",
        "views/family_dependents_menu_views.xml",
        "views/penta_vacation_report_views.xml",
        "views/hr_payslip_run_views.xml",
        "views/hr_payslip_run_views_import.xml",
        "views/import_monthly_inputs_views.xml",
        "views/hr_salary_rule_views_in.xml",
        'views/hr_payslip_views.xml',
        "views/res_partner_bank.xml",
        
        "wizard/payroll_report_wizard.xml",
        
    ],
    "installable": True,
    "application": False,
    "images": ["static/description/icon.svg", "static/description/banner.svg"],
    "post_init_hook": "post_init_create_calendar_40",
}
