# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAssetTemplate(models.Model):
    _name = 'account.asset.template'
    _description = 'Fixed Asset Records Template'
    _rec_name = 'name'
    
    name = fields.Char(required=True)
    body_html = fields.Html(string="Contents of the Minutes", render_engine='qweb', render_options={'post_process': True},
                            prefetch=True, translate=True, sanitize='email_outgoing')
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_name_company', 'unique(name, company_id)', 'A template with that name already exists for this company.')
    ]