# -*- coding: utf-8 -*-
from odoo import models, fields, api
import base64
import io
from odoo.tools.misc import xlsxwriter
from odoo.addons.penta_base.reports.xlsx_formats import get_xlsx_formats

class ReportSalesWithholdingWizard(models.TransientModel):
	_name = 'report.sales.withholding.wizard'
	_description = 'Wizard to generate sales withholdings report'

	date_start = fields.Date(string='Desde', required=True)
	date_end = fields.Date(string='Hasta', required=True)
	retention_type = fields.Selection([
		('IVA', 'Retención IVA'),
		('Fuente', 'Retención Fuente'),
		('Todos', 'Todos'),
	], string='Tipo de Retención', required=True, default='Todos')
	apply_percentage_filter = fields.Boolean(string='Aplicar filtro de porcentaje')
	# Modo exacto (operador + valor) o rango (min/max)
	use_percentage_range = fields.Boolean(string='Usar rango de porcentaje')
	percentage_operator = fields.Selection([
		('=', 'Igual a'),
		('>=', 'Mayor o igual'),
		('<=', 'Menor o igual'),
		('>', 'Mayor que'),
		('<', 'Menor que'),
	], string='Operador porcentaje?', default='=')
	percentage_value = fields.Float(string='Valor porcentaje?')
	percentage_min = fields.Float(string='Porcentaje mínimo?')
	percentage_max = fields.Float(string='Porcentaje máximo?')

	show_percentage_exact_fields = fields.Boolean(compute='_compute_show_percentage_fields', store=False)
	show_percentage_range_fields = fields.Boolean(compute='_compute_show_percentage_fields', store=False)

	@api.depends('apply_percentage_filter', 'use_percentage_range')
	def _compute_show_percentage_fields(self):
		for rec in self:
			rec.show_percentage_exact_fields = bool(rec.apply_percentage_filter and not rec.use_percentage_range)
			rec.show_percentage_range_fields = bool(rec.use_percentage_range)

	@api.onchange('apply_percentage_filter')
	def _onchange_apply_percentage_filter(self):
		for rec in self:
			if rec.apply_percentage_filter:
				# Si activa modo exacto, desactivar rango
				rec.use_percentage_range = False
				# Limpiar campos de rango
				rec.percentage_min = 0.0
				rec.percentage_max = 0.0

	@api.onchange('use_percentage_range')
	def _onchange_use_percentage_range(self):
		for rec in self:
			if rec.use_percentage_range:
				# Si activa rango, desactivar modo exacto
				rec.apply_percentage_filter = False
				# Limpiar campo exacto
				rec.percentage_value = 0.0

	def _compare_percent(self, percent: float) -> bool:
		"""
		Aplica el filtro de porcentaje según configuración:
		- Si use_percentage_range: filtra por [min, max] cuando estén definidos.
		- Caso contrario: aplica operador con percentage_value.
		"""
		if self.use_percentage_range:
			min_v = self.percentage_min
			max_v = self.percentage_max
			# Permitir que el usuario ingrese min > max (intercambiar)
			if min_v and max_v and min_v > max_v:
				min_v, max_v = max_v, min_v
			if min_v and percent < min_v:
				return False
			if max_v and percent > max_v:
				return False
			return True
		# Modo exacto (operador + valor)
		op = self.percentage_operator
		val = self.percentage_value
		# Si no ingresó valor y operador por defecto '=', no filtrar
		if op == '=' and not val:
			return True
		if op == '=':
			return percent == val
		if op == '>=':
			return percent >= val
		if op == '<=':
			return percent <= val
		if op == '>':
			return percent > val
		if op == '<':
			return percent < val
		return True

	def _get_moves_data(self):
		# Retenciones en ventas: movimientos publicados con fecha de retención en rango
		# y con líneas de retención vinculadas a facturas de venta.
		move_domain = [
			('state', '=', 'posted'),
			('l10n_ec_withhold_date', '>=', self.date_start),
			('l10n_ec_withhold_date', '<=', self.date_end),
			('line_ids.l10n_ec_withhold_tax_amount', '!=', 0),
		]
		return self.env['account.move'].search(move_domain, order='l10n_ec_withhold_date asc')

	def print_report(self):
		report = self.generate_xlsx_report()
		today = fields.Date.context_today(self)
		file_name = f"retenciones_ventas_{today.strftime('%d%m%Y')}.xlsx"
		attachment = self.env['ir.attachment'].create({
			'name': file_name,
			'type': 'binary',
			'datas': base64.b64encode(report),
			'res_model': self._name,
			'res_id': self.id,
			'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
		})
		return {
			'type': 'ir.actions.act_url',
			'url': f'/web/content/{attachment.id}?download=true',
			'target': 'self',
		}

	def generate_xlsx_report(self):
		output = io.BytesIO()
		workbook = xlsxwriter.Workbook(output, {'in_memory': True})
		worksheet = workbook.add_worksheet("Retenciones Ventas")
		formats = get_xlsx_formats(workbook)
		DATE_FMT = '%d/%m/%Y'

		# Ancho de columnas y filas
		worksheet.set_row(0, 18)
		worksheet.set_column('A:N', 18)

		# Encabezado de reporte
		company_name = self.env.company.display_name
		worksheet.merge_range('A1:E1', company_name)
		worksheet.merge_range('A2:B2', 'Fecha Desde:')
		worksheet.write('C2', self.date_start.strftime(DATE_FMT) if self.date_start else '')
		worksheet.merge_range('A3:B3', 'Fecha Hasta:')
		worksheet.write('C3', self.date_end.strftime(DATE_FMT) if self.date_end else '')
		worksheet.merge_range('A4:B4', 'Reporte:')
		worksheet.write('C4', 'RETENCIONES VENTAS')

		# Cabeceras (agregada CUENTA CONTABLE tras VALOR RETENIDO)
		headers = [
			'#', 'FECHA DE EMISIÓN', 'NÚMERO DE RETENCIÓN', 'RUC', 'RAZÓN SOCIAL', 'AUTORIZACIÓN SRI',
			'BASE IMPONIBLE', 'VALOR RETENIDO', 'CUENTA CONTABLE', 'PORCENTAJE', 'TIPO', 'CASILLA 104', 'NRO FACTURA', 'FECHA FACTURA'
		]
		row = 5
		for col, header in enumerate(headers):
			worksheet.write(row, col, header, formats['header_bg'])

		# Datos
		row += 1
		count = 1
		moves = self._get_moves_data()
		for move in moves:
			# Recorremos únicamente líneas con monto retenido; Casilla 104 se determina por línea.
			for line in move.line_ids:
				if not line.l10n_ec_withhold_tax_amount:
					continue
				# Filtrar solo retenciones de clientes: partner con customer_rank > 0
				if move.partner_id and move.partner_id.customer_rank <= 0:
					continue
				# Factura origen (puede no existir; se muestran retenciones con o sin factura asociada)
				# Tipo (grupo de impuestos)
				tax_groups = line.tax_ids.mapped('tax_group_id')
				group_name = tax_groups[:1].name if tax_groups else ''
				# Normalizar tipo a 'IVA' o 'Fuente' a partir del nombre del grupo
				normalized = group_name or ''
				if group_name:
					lower = group_name.lower()
					if 'iva' in lower:
						normalized = 'IVA'
					elif 'fuente' in lower or 'renta' in lower:
						normalized = 'Fuente'
				if self.retention_type != 'Todos' and normalized != self.retention_type:
					continue

				# Porcentaje
				percent_vals = [abs(t.amount) for t in line.tax_ids if t.amount_type == 'percent']
				percent = percent_vals[0] if percent_vals else 0.0
				if (self.apply_percentage_filter or self.use_percentage_range) and not self._compare_percent(percent):
					continue

				# Factura origen
				invoice = line.l10n_ec_withhold_invoice_id

				worksheet.write(row, 0, count, formats['center'])
				withhold_date = getattr(move, 'l10n_ec_withhold_date', None)
				worksheet.write(row, 1, withhold_date.strftime(DATE_FMT) if withhold_date else '', formats['border'])
				# worksheet.write(row, 2, move.journal_id.name or '', formats['border'])
				# Número de retención: solo dígitos
				import re
				raw_ret = move.name or ''
				ret_digits = re.sub(r'\D', '', raw_ret)
				worksheet.write(row, 2, ret_digits if ret_digits else raw_ret, formats['border'])
				worksheet.write(row, 3, move.partner_id.vat or '', formats['border'])
				worksheet.write(row, 4, move.partner_id.complete_name or '', formats['border'])
				worksheet.write(row, 5, move.l10n_ec_authorization_number or '', formats['border'])
				# Base imponible siempre en positivo
				worksheet.write(row, 6, abs(line.balance) if line.balance else 0.0, formats['currency'])
				worksheet.write(row, 7, line.l10n_ec_withhold_tax_amount or 0.0, formats['currency'])
				# Cuenta contable: código + nombre (si existe)
				account_label = ''
				if line.account_id:
					acc_code = line.account_id.code or ''
					acc_name = line.account_id.name or ''
					account_label = f"{acc_code} {acc_name}".strip()
				worksheet.write(row, 8, account_label, formats['border'])
				worksheet.write(row, 9, (percent / 100.0), formats['percent'])
				# Tipo normalizado en base al grupo de impuestos
				worksheet.write(row, 10, normalized or (group_name or ''), formats['center'])
				# Casilla 104 por línea: prioridad tax_tag_ids; fallback código ATS de impuestos
				line_tag_names = line.tax_tag_ids.mapped('name') if line.tax_tag_ids else []
				if line_tag_names:
					casilla_104 = line_tag_names[0]
				else:
					ats_codes = [t.l10n_ec_code_ats for t in line.tax_ids if getattr(t, 'l10n_ec_code_ats', False)]
					casilla_104 = ats_codes[0] if ats_codes else ''
				worksheet.write(row, 11, casilla_104, formats['border'])
				worksheet.write(row, 12, invoice.name if invoice else '', formats['border'])
				worksheet.write(row, 13, invoice.invoice_date.strftime(DATE_FMT) if invoice and invoice.invoice_date else '', formats['border'])

				row += 1
				count += 1

		workbook.close()
		output.seek(0)
		return output.read()