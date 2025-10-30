# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re


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
    brand = fields.Char('Marca', tracking=True)
    model = fields.Char('Modelo', tracking=True)
    serial_number = fields.Char('Número de Serie', tracking=True)
    location = fields.Char('Ubicación física', tracking=True)
    department_id = fields.Many2one('hr.department', string='Departamento o Área', tracking=True)
    photo_info = fields.Html('Otra información relevante')
    plate = fields.Char(tracking=True)
    color = fields.Char(tracking=True)

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
