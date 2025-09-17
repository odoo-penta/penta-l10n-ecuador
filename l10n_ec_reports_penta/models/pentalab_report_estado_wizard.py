from datetime import datetime
from odoo import models, fields, api
import base64

from odoo.exceptions import UserError

class PentalabReportEstadoWizard(models.TransientModel):
    _name = 'pentalab.report.estado.wizard'
    _description = 'Wizard para Generar Reporte Modificado'

    date_to = fields.Date(string="Fecha Final", required=True)
    date_from = fields.Date(string="Fecha Inicio", required=True)
    report_file = fields.Binary(string="Reporte Generado", readonly=True)
    report_filename = fields.Char(string="Nombre del Archivo", default="estado_resultados.xlsx")

    def extraer_options_generico(self, company_id, report_id, date_to,date_from):
        """
        Genera opciones dinámicas para cualquier reporte financiero en Odoo.

        :param company_id: ID de la empresa
        :param report_id: ID del reporte
        :param date_from: Fecha de inicio en formato date
        :param date_to: Fecha de fin en formato date
        :return: Diccionario con las opciones generadas
        """
        company = self.env['res.company'].browse(company_id)

        options = {
            'companies': [{'id': company.id, 'name': company.name, 'currency_id': company.currency_id.id}],
            'report_id': report_id,
            'selected_variant_id': report_id,  # Normalmente coincide con report_id
            'sections_source_id': report_id,  # También suele coincidir
            'sections': [],
            'has_inactive_sections': False,
            'has_inactive_variants': False,
            'allow_domestic': True,
            'fiscal_position': 'all',
            'available_vat_fiscal_positions': [],
            'date': {
                'date_to': date_to.strftime("%Y-%m-%d"),
                'date_from': date_from.strftime("%Y-%m-%d"),
            },
            'comparison': {
                'filter': 'no_comparison',
            },
            'export_mode': 'file',
            'all_entries': False,
            'journals': self._get_active_journals(company_id),  # Obtiene los diarios activos
            'selected_journal_groups': {},
            'name_journal_group': 'All Journals',
            'loading_call_number': 2,
            'multi_currency': company.currency_id.id is not None,
            'unreconciled': False,
            'rounding_unit': 'decimals',
            'unfold_all': True,
            'unfolded_lines': [],
            'show_debug_column': True,
            'hierarchy': True,
            'display_hierarchy_filter': True,
            'readonly_query': True,
        }

        return options

    def _get_active_journals(self, company_id):
        """
        Obtiene los diarios activos para la empresa dada.

        :param company_id: ID de la empresa
        :return: Lista de diccionarios con los diarios activos
        """
        journals = self.env['account.journal'].search([('company_id', '=', company_id), ('active', '=', True)])
        return [
            {
                'id': journal.id,
                'model': 'account.journal',
                'name': journal.name,
                'selected': False,
                'title': journal.name,
                'type': journal.type,
                'visible': True
            }
            for journal in journals
        ]

    def action_generate_report(self):
        if self.date_to < self.date_from:
            raise UserError("La fecha final no puede ser menor a la fecha inicial.")
        """Genera el reporte y almacena el archivo en el wizard"""
        company_id = self.env.company.id  # Obtener la empresa actual
        report_id = 24  # ID del reporte fijo
        ultimo_dia = self.date_to.strftime('%d-%m-%Y')  # Formatear la fecha como espera el método
        primer_dia = self.date_from.strftime('%d-%m-%Y') 
        date_to = datetime.strptime(ultimo_dia, '%d-%m-%Y').date()
        date_from = datetime.strptime(primer_dia, '%d-%m-%Y').date()
        options = self.extraer_options_generico(company_id,report_id,date_to,date_from)
        # Llamar al método que genera el reporte
        self.env['pentalab.report.custom'].generar_reporte_modificado(company_id, report_id,options)

        # Leer el archivo generado y almacenarlo en el campo binario
        file_path = 'reporte_modificado.xlsx'
        with open(file_path, 'rb') as file:
            file_content = file.read()
            self.report_file = base64.b64encode(file_content)
            self.report_filename = 'Estado_Resultados_%s_%s.xlsx' % (self.date_from,self.date_to)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pentalab.report.estado.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
