# -*- coding: utf-8 -*-
from odoo import api, fields, models
from calendar import monthrange
from datetime import date, timedelta

class PentaBenefitConfig(models.Model):
    _name = "penta.benefit.config"
    _description = "Configuración períodos de beneficios (13ro/14to/Utilidades)"
    _rec_name = "name"

    benefit_key = fields.Selection([
        ("13th", "Décimo Tercer Sueldo"),
        ("14_costa", "Décimo Cuarto - Costa/Galápagos"),
        ("14_sierra", "Décimo Cuarto - Sierra/Amazonía"),
        ("utilities", "Utilidades"),
    ], required=True, index=True)
    name = fields.Char(required=True)

    # Regla por defecto (día/mes inicio-fin, sin año)
    start_month = fields.Integer("Mes inicio", required=True)   # 1..12
    start_day = fields.Integer("Día inicio", required=True)     # 1..31
    end_month   = fields.Integer("Mes fin", required=True)      # 1..12
    end_day     = fields.Integer("Día fin", required=True)      # 1..31
    crosses_year = fields.Boolean(
        "Cruza año", 
        help="Marcar si el fin cae en el año siguiente (p.ej. Mar 1 → Feb último del siguiente)."
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)

    _sql_constraints = [
        ("benefit_key_company_uniq", "unique(benefit_key, company_id)",
         "Ya existe una configuración para este beneficio en la compañía."),
    ]

    # calcular rango dado un año base 
    @api.model
    def compute_period_for_year(self, benefit_key, ref_date=None):
        """Devuelve (date_start, date_end) usando esta configuración.
        ref_date por defecto: hoy(). 
        Regla:
          - Si crosses_year=True: start en el año actual y end en el año +1,
            o según corresponda al beneficio (ver keys).
          - Si crosses_year=False: start/end en el mismo año (o desplazados según key).
        """
        cfg = self.search([("benefit_key", "=", benefit_key),
                           ("company_id", "=", self.env.company.id)], limit=1)
        if not cfg:
            return None, None

        today = ref_date or fields.Date.context_today(self)
        # Normalizamos a date
        if isinstance(today, str):
            y, m, d = map(int, today.split("-"))
            today = date(y, m, d)

        y = today.year

        if benefit_key == "13th":
            # 1 Dic (año-1) → 30 Nov (año)
            start_y = y - 1
            end_y = y
            start_m, start_d = 12, 1
            end_m, end_d = 11, 30

        elif benefit_key == "14_costa":
            # 1 Mar (año) → último día Feb (año+1)
            start_y = y
            end_y = y + 1
            start_m, start_d = 3, 1
            end_m, end_d = 2, monthrange(end_y, 2)[1]  # febrero variable

        elif benefit_key == "14_sierra":
            # 1 Ago (año-1) → 31 Jul (año)
            start_y = y - 1
            end_y = y
            start_m, start_d = 8, 1
            end_m, end_d = 7, 31

        elif benefit_key == "utilities":
            # 1 Ene (año-1) → 31 Dic (año-1)
            start_y = y - 1
            end_y = y - 1
            start_m, start_d = 1, 1
            end_m, end_d = 12, 31

        else:
            # Fallback a config general de la tabla (start/end + crosses_year)
            start_y = y
            end_y = y + 1 if cfg.crosses_year else y
            start_m, start_d = cfg.start_month, cfg.start_day
            end_m, end_d = cfg.end_month, cfg.end_day
            if end_m == 2 and end_d > 28:
                end_d = monthrange(end_y, 2)[1]

        d_start = date(start_y, start_m, min(start_d, monthrange(start_y, start_m)[1]))
        d_end   = date(end_y,   end_m,   min(end_d,   monthrange(end_y,   end_m)[1]))
        return d_start, d_end
