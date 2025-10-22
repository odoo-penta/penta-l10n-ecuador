# -*- coding: utf-8 -*-
from odoo import models, fields, api
import base64
import io
from odoo.tools.misc import xlsxwriter
from odoo.addons.penta_base.reports.xlsx_formats import get_xlsx_formats
from odoo.tools import format_invoice_number


class ReportSalesWithholdingWizard(models.TransientModel):
	_name = 'report.sales.withholding.wizard'
	_description = 'Wizard to generate sales withholdings report'

	date_start = fields.Date(string='Desde', required=True)
	date_end = fields.Date(string='Hasta', required=True)
	retention_type = fields.Selection([
		('all', 'Todos'),
		('vat_withholding', 'Retención IVA'),
		('income_withholding', 'Retención Fuente')
		], string='Tipo de Retención', required=True, default='all')
	apply_percentage_filter = fields.Boolean(string='Aplicar filtro de porcentaje')
	# Modo exacto (operador + valor) o rango (min/max)
	use_percentage_range = fields.Boolean(string='Usar rango de porcentaje')
	percentage_operator = fields.Selection([
		('=', 'Igual a'),
		('>=', 'Mayor o igual'),
		('<=', 'Menor o igual'),
		('>', 'Mayor que'),
		('<', 'Menor que'),
	], string='Operador porcentaje', default='=')
	percentage_value = fields.Float(string='Valor porcentaje')
	percentage_min = fields.Float(string='Porcentaje mínimo')
	percentage_max = fields.Float(string='Porcentaje máximo')
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
		# Generar data para reporte
		move_domain = [
			('state', '=', 'posted'),
			('l10n_ec_withhold_date', '>=', self.date_start),
			('l10n_ec_withhold_date', '<=', self.date_end),
			('journal_id.l10n_ec_withhold_type', '=', 'out_withhold'),
		]
		return self.env['account.move'].search(move_domain, order='l10n_ec_withhold_date asc')

	def print_report(self):
		report = self.generate_xlsx_report()
		today = fields.Date.context_today(self)
		file_name = f"RetencionesVentas_{today.strftime('%d_%m_%Y')}.xlsx"
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
		# Formatos
		formats = get_xlsx_formats(workbook)
		DATE_FMT = '%d/%m/%Y'
		# Ancho de columnas y filas
		worksheet.set_column('A:A', 6)
		worksheet.set_column('B:C', 24)
		worksheet.set_column('D:D', 15)
		worksheet.set_column('E:E', 30)
		worksheet.set_column('F:G', 20)
		worksheet.set_column('H:I', 22)
		worksheet.set_column('J:J', 20)
		worksheet.set_column('K:L', 25)
		worksheet.set_column('M:M', 20)
		worksheet.set_column('N:N', 35)
		# Encabezados
		headers = [
			'#', 'FECHA DE EMISIÓN', 'NÚMERO DE RETENCIÓN', 'RUC', 'RAZÓN SOCIAL', 'AUTORIZACIÓN SRI', 'TIPO RETENCIÓN',
			'BASE IMPONIBLE', 'VALOR RETENIDO', 'PORCENTAJE', 'CASILLA 104', 'NRO FACTURA', 'FECHA FACTURA', 'CUENTA CONTABLE'
		]
		# Mapear cabecera
		company_name = self.env.company.display_name
		worksheet.merge_range('A1:E1', company_name)
		worksheet.merge_range('A2:B2', 'Fecha Desde:')
		worksheet.write('C2', self.date_start.strftime(DATE_FMT) if self.date_start else '')
		worksheet.merge_range('A3:B3', 'Fecha Hasta:')
		worksheet.write('C3', self.date_end.strftime(DATE_FMT) if self.date_end else '')
		worksheet.merge_range('A4:B4', 'Reporte:')
		worksheet.write('C4', 'RETENCIONES VENTAS')
		row = 5
		for col, header in enumerate(headers):
			worksheet.write(row, col, header, formats['header_bg'])
		# Mapear datos
		row += 1
		count = 1
		moves = self._get_moves_data()
		iva_tax_groups = self.env['account.tax.group'].search([('type_ret', 'in', ['withholding_iva_sales'])])
		rent_tax_groups = self.env['account.tax.group'].search([('type_ret', 'in', ['withholding_rent_sales'])])
		for move in moves:
			invoice = move.line_ids.mapped('l10n_ec_withhold_invoice_id').id
			if invoice:
				invoice = self.env['account.move'].browse(invoice)
			# Recorremos únicamente líneas con monto retenido; Casilla 104 se determina por línea.
			for reten in move.l10n_ec_withhold_line_ids:
				# Aplicar filtro de tipo de retencion
				is_vat = reten.tax_ids.tax_group_id.id in iva_tax_groups.ids
				is_income = reten.tax_ids.tax_group_id.id in rent_tax_groups.ids
				if self.retention_type == 'vat_withholding' and not is_vat:
					continue
				if self.retention_type == 'income_withholding' and not is_income:
					continue
				if not reten.l10n_ec_withhold_tax_amount:
					continue
				# Aplicar filtro de porcentaje si corresponde
				percent = abs(reten.tax_ids.amount)
				if self.apply_percentage_filter or self.use_percentage_range:
					if not self._compare_percent(percent):
						continue
				worksheet.write(row, 0, count, formats['center'])
				withhold_date = getattr(move, 'l10n_ec_withhold_date', None)
				worksheet.write(row, 1, withhold_date.strftime(DATE_FMT) if withhold_date else '', formats['border'])
				# Número de retencion
				worksheet.write(row, 2, format_invoice_number(move.ref) if move.ref else move.name, formats['border'])
				worksheet.write(row, 3, move.partner_id.vat or '', formats['border'])
				worksheet.write(row, 4, move.partner_id.complete_name or '', formats['border'])
				worksheet.write(row, 5, move.l10n_ec_authorization_number or '', formats['border'])
				# Tipo de retencion
				if self.retention_type == 'vat_withholding':
					worksheet.write(row, 6, 'IVA', formats['center'])
				elif self.retention_type == 'income_withholding':
					worksheet.write(row, 6, 'RENTA', formats['center'])
				else:
					if is_vat:
						worksheet.write(row, 6, 'IVA', formats['center'])
					else:
						worksheet.write(row, 6, 'RENTA', formats['center'])
				# Base imponible siempre en positivo
				worksheet.write(row, 7, abs(reten.balance) if reten.balance else 0.0, formats['currency'])
				worksheet.write(row, 8, reten.l10n_ec_withhold_tax_amount or 0.0, formats['currency'])
				worksheet.write(row, 9, (percent / 100.0), formats['percent'])
				iva_tags = []
				rent_tags = []
				for line in move.line_ids:
					for tag in line.tax_tag_ids:
						if 'IVA' in line.name.upper():
							iva_tags.append(tag.name)
						else:
							rent_tags.append(tag.name)
    			# Casilla 104
				if is_vat:
					worksheet.write(row, 10, iva_tags[0] if iva_tags else '', formats['border'])
				elif is_income:
					worksheet.write(row, 10, rent_tags[0] if rent_tags else '', formats['border'])
				worksheet.write(row, 11, format_invoice_number(invoice.name) if invoice else '', formats['border'])
				worksheet.write(row, 12, invoice.invoice_date.strftime(DATE_FMT) if invoice and invoice.invoice_date else '', formats['border'])
				# Obtener cuenta contable
				account_name = ''
				for line in move.line_ids:
					if line.tax_line_id == reten.tax_ids:
						if line.account_id.code:
							account_name = line.account_id.code + ' ' + line.account_id.name
						else:
							account_name = line.account_id.name
						break
				worksheet.write(row, 13, account_name, formats['border'])
				row += 1
				count += 1
		workbook.close()
		output.seek(0)
		return output.read()
