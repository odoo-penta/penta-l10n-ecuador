# -*- coding: utf-8 -*-
from odoo import fields, models, _
from collections import defaultdict

MAX_NAME_LENGTH = 50


class AssetsReportCustomHandler(models.AbstractModel):
    _inherit = 'account.asset.report.handler'

    def _query_lines(self, options, prefix_to_match=None, forced_account_id=None):
        """
        Extender el método original para incluir el asset_code
        """
        lines = []
        asset_lines = self._query_values(options, prefix_to_match=prefix_to_match, forced_account_id=forced_account_id)

        parent_lines = []
        children_lines = defaultdict(list)
        for al in asset_lines:
            if al['parent_id']:
                children_lines[al['parent_id']] += [al]
            else:
                parent_lines += [al]

        # Cache de activos para obtener el código
        asset_ids = [al['asset_id'] for al in parent_lines]
        assets_cache = {asset.id: asset for asset in self.env['account.asset'].browse(asset_ids)}

        for al in parent_lines:
            asset_children_lines = children_lines[al['asset_id']]
            asset_parent_values = self._get_parent_asset_values(options, al, asset_children_lines)
            
            # Obtener el asset_code del cache
            asset = assets_cache.get(al['asset_id'])
            asset_code = getattr(asset, 'asset_code', None) if asset else None
            # Asegurar que sea string vacío si es None o False
            asset_code = asset_code or ''

            # Format the data - AGREGAR asset_code
            columns_by_expr_label = {
                "asset_code": asset_code,  # NUEVA COLUMNA
                "acquisition_date": al["asset_acquisition_date"] and self._format_date_for_report(al["asset_acquisition_date"]) or "",
                "first_depreciation": al["asset_date"] and self._format_date_for_report(al["asset_date"]) or "",
                "method": (al["asset_method"] == "linear" and _("Linear")) or (al["asset_method"] == "degressive" and _("Declining")) or _("Dec. then Straight"),
                **asset_parent_values
            }

            lines.append((al['account_id'], al['asset_id'], al['asset_group_id'], columns_by_expr_label))
        return lines
    
    def _format_date_for_report(self, date_value):
        """Helper para formatear fechas"""
        try:
            from odoo.tools import format_date
            return format_date(self.env, date_value)
        except:
            return str(date_value) if date_value else ""

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        
        # Actualizar los subheaders para incluir la nueva columna
        options['custom_columns_subheaders'] = [
            {"name": _("Características"), "colspan": 5},  # Aumentado de 4 a 5
            {"name": _("Activos"), "colspan": 4},
            {"name": _("Depreciación"), "colspan": 4},
            {"name": _("Valor contable"), "colspan": 1}
        ]
