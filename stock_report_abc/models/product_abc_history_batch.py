# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

ABC_CLASSIFICATION_SELECTION = [
    ('A', 'A'), ('B', 'B'), ('C', 'C'),
    ('D', 'D'), ('E', 'E'), ('F', 'F')
]

class ProductAbcHistoryBatch(models.Model):
    _name = 'product.abc.history.batch'
    _description = 'Historial ABC - Cabecera por Mes'
    _order = 'year desc, month desc, id desc'
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True, index=True)
    year = fields.Integer(required=True, index=True)
    month = fields.Integer(required=True, index=True)
    line_ids = fields.One2many('product.abc.history.line', 'batch_id', string='Líneas')
    line_count = fields.Integer(compute='_compute_line_count', store=False)
    snapshot_date = fields.Date(string='Fecha de snapshot', help="Fecha efectiva (último día del mes anterior).")

    _sql_constraints = [
        ('uniq_company_year_month', 'unique(company_id, year, month)',
         'Ya existe un historial para esa compañía y mes.')
    ]

    @api.depends('year', 'month')
    def _compute_name(self):
        for r in self:
            if r.year and r.month:
                r.name = f"{r.year}-{int(r.month):02d}"
            else:
                r.name = "-"

    def _compute_line_count(self):
        for r in self:
            r.line_count = len(r.line_ids)

    def action_open_lines(self):
        """Abrir la lista de productos del historial (vista tipo lista)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Historial ABC - %s') % (self.name or ''),
            'res_model': 'product.abc.history.line',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {'default_batch_id': self.id},
            'target': 'current',
            'search_view_id': self.env.ref(
                'stock_report_abc.view_product_abc_history_line_search'
            ).id,
        }

