# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import date
import re
from html import unescape
from odoo.exceptions import ValidationError, UserError
from odoo.tools import month_name_es


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    asset_code = fields.Char(
        string='Código del Activo',
        help='Código único alfanumérico para identificar el activo (ej: EQP-001, MOB2025)',
        size=30,
        index=True,
        tracking=True
    )
    custodian_id = fields.Many2one('hr.employee', string='Custodio', tracking=True)
    brand_id = fields.Many2one('product.brand', tracking=True)
    model = fields.Char('Modelo', tracking=True)
    serial_number = fields.Char('Número de Serie', tracking=True)
    location_id = fields.Many2one('hr.work.location', tracking=True)
    department_id = fields.Many2one('hr.department', string='Departamento o Área', tracking=True)
    photo_info = fields.Html('Otra información relevante')
    plate = fields.Char(tracking=True)
    color = fields.Char(tracking=True)
    characteristics = fields.Html()
    analytic_distribution_text = fields.Char(
        string="Distribución analítica",
        compute="_compute_analytic_distribution_text",
        store=True,
        tracking=True,
    )

    @api.depends('analytic_distribution')
    def _compute_analytic_distribution_text(self):
        for rec in self:
            names = []
            dist = rec.analytic_distribution or {}
            for key in dist.keys():
                # Convertir a string y limpiar espacios
                key_str = str(key).strip()
                # Si tiene varias claves separadas por coma → recorrer todas
                key_parts = [p.strip() for p in key_str.split(',') if p.strip()]
                for part in key_parts:
                    try:
                        acc_id = int(part)
                        acc = self.env['account.analytic.account'].browse(acc_id)
                        if acc.exists():
                            names.append(acc.name)
                    except (ValueError, TypeError):
                        continue
            # Unir los nombres con coma y espacio
            rec.analytic_distribution_text = ', '.join(names)

    @api.constrains('asset_code')
    def _check_asset_code_unique(self):
        """Validar que el código del activo sea único"""
        for record in self:
            if record.asset_code:
                # Buscar otros registros con el mismo código (excluyendo el registro actual)
                existing_asset = self.search([
                    ('asset_code', '=', record.asset_code),
                    ('id', '!=', record.id)
                ], limit=1)
                
                if existing_asset:
                    raise ValidationError(
                        _("El código ingresado ya existe, por favor ingrese uno diferente.")
                    )

    @api.constrains('asset_code')
    def _check_asset_code_format(self):
        """Validar el formato del código del activo"""
        # Permitir letras, números y caracteres especiales imprimibles (por ejemplo: _ - / *)
        # Se permiten espacios y cualquier caracter imprimible ASCII.
        pattern = r'^[\x20-\x7E]+$'
        for record in self:
            if record.asset_code:
                if not re.match(pattern, record.asset_code):
                    raise ValidationError(
                        _(
                            "El código del activo sólo puede contener caracteres imprimibles (letras, números y símbolos como _ - / *)."
                        )
                    )

    def write(self, vals):
        """Sobrescribir write para registrar cambios en el chatter"""
        old_codes = {}
        if 'asset_code' in vals:
            for record in self:
                old_codes[record.id] = record.asset_code
        
        result = super(AccountAsset, self).write(vals)
        
        # Registrar cambio en el chatter si el código fue modificado
        if 'asset_code' in vals:
            for record in self:
                old_code = old_codes.get(record.id)
                new_code = record.asset_code
                
                if old_code != new_code:
                    if old_code and new_code:
                        message = _("Código del activo modificado de '%s' a '%s'") % (old_code, new_code)
                    elif old_code and not new_code:
                        message = _("Código del activo eliminado (era '%s')") % old_code
                    elif not old_code and new_code:
                        message = _("Código del activo establecido como '%s'") % new_code
                    else:
                        continue
                    
                    record.message_post(
                        body=message,
                        message_type='notification',
                        subtype_xmlid='mail.mt_note'
                    )
        
        return result

    @api.constrains('asset_code')
    def _check_asset_code_unique(self):
        """Validar que el código del activo sea único"""
        for record in self:
            if record.asset_code:
                existing = self.search([
                    ('asset_code', '=', record.asset_code),
                    ('id', '!=', record.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_(
                        'Ya existe un activo con el código "%s". El código del activo debe ser único.'
                    ) % record.asset_code)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        """Permitir búsqueda por código del activo"""
        args = args or []
        if name:
            # Buscar tanto por nombre como por código
            domain = ['|', ('name', operator, name), ('asset_code', operator, name)]
            return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
        return super()._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)

    def action_print_assets_report(self):
        # validar que seleccionemos registros
        if not self:
            raise UserError(_("You must select at least one asset to generate the record."))
        # Obtener plantilla desde configuración contable
        template_id = self.env['ir.config_parameter'].sudo().get_param('l10n_ec_account_penta.asset_template_id')
        if not template_id:
            raise UserError(_("A fixed asset record template has not been configured in the accounting settings."))
        # Validar que la plantilla exista
        template = self.env['account.asset.template'].browse(int(template_id))
        if not template.exists():
            raise UserError(_("The configured template no longer exists or has been deleted."))
        # Validar custodios
        custodians = self.mapped('custodian_id')
        if not custodians or any(not c for c in custodians):
            raise UserError(_("All selected assets must have an assigned custodian."))
        if len(custodians) > 1:
            raise UserError(_("All selected assets must belong to the same custodian."))
        # Validar campos de la plantilla
        placeholders = re.findall(r'\{(.*?)\}', template.body_html or "")
        allowed = [
            'fecha', 'dia', 'mes', 'anio',
            'empresa',
            'custodio', 'custodio_ci', 'custodio_cargo',
            'partner', 'partner_ci', 'partner_cargo',
            'activos'
        ]
        missing = [p for p in placeholders if p not in allowed]
        if missing:
            raise UserError(f"The template uses unknown fields: {', '.join(missing)}")
        # Mapeamos los datos necesarios
        company = self.company_id
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        partner_name = ''
        partner_ci = ''
        partner_cargo = ''
        if employee:
            partner_name = employee.name
            partner_ci = employee.identification_id or ''
            partner_cargo = employee.job_id.name if employee.job_id else ''
        else:
            partner_name = self.env.user.partner_id.name
        custodian = custodians[0]
        today = date.today()
        state_vals = {
            'model': 'Modelo',
            'draft': 'Borrador',
            'open': 'En proceso',
            'paused': 'En espera',
            'close': 'Cerrado',
            'cancelled': 'Candelado',
        }
        # Mapeamos la tabla de activos
        activos_html = """
        <table style="width:100%; border-collapse: collapse; margin-top: 10px;" border="1">
        <thead>
            <tr style="background-color:#f2f2f2; text-align:center;">
            <th style="padding:8px;">Código</th>
            <th style="padding:8px;">Descripción</th>
            <th style="padding:8px;">Modelo</th>
            <th style="padding:8px;">Marca</th>
            <th style="padding:8px;">Serie</th>
            <th style="padding:8px;">Características</th>
            <th style="padding:8px;">Estado</th>
            <th style="padding:8px;">Observaciones</th>
            </tr>
        </thead>
        <tbody>
        """
        for a in self:
            activos_html += f"""
            <tr>
            <td style="padding:6px;">{a.asset_code or ''}</td>
            <td style="padding:6px;">{a.name or ''}</td>
            <td style="padding:6px;">{a.model or ''}</td>
            <td style="padding:6px;">{a.brand.name if a.brand else ''}</td>
            <td style="padding:6px;">{a.serial_number or ''}</td>
            <td style="padding:6px;">{a.characteristics or ''}</td>
            <td style="padding:6px;">{state_vals.get(a.state) or ''}</td>
            <td style="padding:6px;">{a.photo_info or ''}</td>
            </tr>
            """
        activos_html += """
        </tbody>
        </table>
        """
        # Aplicamos el formato con los datos necesarios
        raw_html = unescape(template.body_html or "")
        html_rendered = raw_html.format(
            fecha=date.today().strftime("%d/%m/%Y"),
            dia=today.day,
            mes=month_name_es(today.month),
            anio=today.year,
            empresa=company.name,
            custodio=custodian.name,
            custodio_ci=custodian.identification_id or '',
            custodio_cargo=custodian.job_id.name if custodian.job_id else '',
            partner=partner_name,
            partner_ci=partner_ci,
            partner_cargo=partner_cargo,
            activos=activos_html,
        )
        # Renderizar el HTML dentro de un contenedor QWeb genérico
        return self.env.ref('l10n_ec_account_penta.action_report_minutes_assets').report_action(
            self, data={'html': html_rendered}
        )
