# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def post_init_create_calendar_40(cr, registry):
    """
    Crea el calendario 'Estandar 40 horas/semana'
    exactamente como si se hiciera desde la UI.
    """

    env = api.Environment(cr, SUPERUSER_ID, {})

    company = env.ref("base.main_company")

    calendar = env.ref("l10n_ec_rrhh_penta.resource_calendar_standard_40")

    # Evitar duplicados (muy importante)
    if calendar.attendance_ids:
        return

    # 1. Crear el calendario (como la UI)
    calendar = env["resource.calendar"].create({
        "name": "Estandar 40 horas/semana",
        "company_id": company.id,
        "tz": "America/Guayaquil",
        "hours_per_day": 8,
        "full_time_required_hours": 40,
        "flexible_hours": False,
    })

    # 2. Crear asistencias (lunes a viernes)
    days = {
        0: "Lunes",
        1: "Martes",
        2: "Miércoles",
        3: "Jueves",
        4: "Viernes",
        5: "Sábado",
        6: "Domingo",
    }

    for day, day_name in days.items():
        # Mañana
        env["resource.calendar.attendance"].create({
            "calendar_id": calendar.id,
            "dayofweek": str(day),
            "day_period": "morning",
            "hour_from": 8,
            "hour_to": 12,
            "work_entry_type_id": False,
            "name": f"{day_name} Mañana",
        })
        # Almuerzo
        env["resource.calendar.attendance"].create({
            "calendar_id": calendar.id,
            "dayofweek": str(day),
            "day_period": "lunch",
            "hour_from": 12,
            "hour_to": 13,
            "work_entry_type_id": False,
            "name": f"{day_name} Almuerzo",
        })
        # Tarde
        env["resource.calendar.attendance"].create({
            "calendar_id": calendar.id,
            "dayofweek": str(day),
            "day_period": "afternoon",
            "hour_from": 13,
            "hour_to": 17,
            "work_entry_type_id": False,
            "name": f"{day_name} Tarde",
        })
