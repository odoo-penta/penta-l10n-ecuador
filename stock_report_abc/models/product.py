# -*- coding: utf-8 -*-
from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import logging
from datetime import date
import calendar
_logger = logging.getLogger(__name__)
import calendar
import time
ABC_CLASSIFICATION_SELECTION = [
    ('A', 'A'),
    ('B', 'B'),
    ('C', 'C'),
    ('D', 'D'),
    ('E', 'E'),
    ('F', 'F')
]

class Product(models.Model):
    _inherit = "product.product"

    annual_sales_qty = fields.Float(string='Cantidad Vendida Anual', store=True)
    abc_classification = fields.Selection(
        selection=ABC_CLASSIFICATION_SELECTION,
        string='Clasificación ABC',
        store=True
    )
    
    months_with_sales_qty = fields.Integer(
        string="Meses con ventas",
        store=True
    )

    categ_name = fields.Char(string='Artículo', store=True)
    categ_group_name = fields.Char(string='Grupo', store=True)
    categ_line_name = fields.Char(string='Línea', store=True)

    has_historical_data = fields.Boolean(string='Incluye Datos Históricos', default=False, store=True)

    sales_m_1 = fields.Float(string="M1",  store=True)
    sales_m_2 = fields.Float(string="M2",  store=True)
    sales_m_3 = fields.Float(string="M3",  store=True)
    sales_m_4 = fields.Float(string="M4",  store=True)
    sales_m_5 = fields.Float(string="M5",  store=True)
    sales_m_6 = fields.Float(string="M6",  store=True)
    sales_m_7 = fields.Float(string="M7",  store=True)
    sales_m_8 = fields.Float(string="M8",  store=True)
    sales_m_9 = fields.Float(string="M9",  store=True)
    sales_m_10 = fields.Float(string="M10",  store=True)
    sales_m_11 = fields.Float(string="M11",  store=True)
    sales_m_12 = fields.Float(string="M12",  store=True)

    costo_total = fields.Float(
        string='Costo Total',
        compute='_compute_costo_total',
        store=True
    )
    
    @api.model
    def action_run_abc_for_cutoff_and_snapshot(self, year, month, batch_size=200, sleep_seconds=0):
        """
        Flujo excepcional que:
        - Fija el corte year/month en TODAS las configuraciones activas.
        - Ejecuta los dos crons reales que ya tienen lógica multi-company.
        """
        if not year or not month:
            raise ValueError("Debe enviar 'year' y 'month'.")

        y_target = int(year)
        m_target = int(month)

        if m_target < 1 or m_target > 12:
            raise ValueError("El parámetro 'month' debe estar entre 1 y 12.")

        # 🔹 1) Actualizar corte en TODAS las companías que tengan config ABC activa
        configs = self.env['abc.classification.config'].sudo().search([
            ('active', '=', True)
        ])
        for cfg in configs:
            cfg.write({'year': y_target, 'month': str(m_target)})

        # 🔹 2) Ejecutar crons reales (ellos YA hacen multi-company)
        self.cron_run_abc_single_loop(
            batch_size=batch_size,
            sleep_seconds=sleep_seconds,
            force=True
        )

        self.cron_snapshot_monthly_abc(
            batch_size=batch_size,
            year=y_target,
            month=m_target,
            force=True
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ABC (flujo excepcional)',
                'message': f'Corte {y_target}-{m_target:02d} clasificado y snapshot guardado.',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def cron_snapshot_monthly_abc(self, batch_size=100, year=False, month=False, force=False):
        """
        Guarda o actualiza el snapshot ABC para el mes y año indicados.
        Si no se especifican `year` y `month`, usa los valores de la configuración ABC activa.
        
        Si ya existe el batch, elimina sus líneas y lo actualiza.
        Si no existe, lo crea.
        """
        today = fields.Date.context_today(self)
        if today.day != 1 and not force:
            _logger.info("[ABC][SNAPSHOT] No es día 1, ejecución omitida.")
            return
    
        Config = self.env['abc.classification.config'].sudo()
    
        companies = self.env['res.company'].search([])
        for company in companies:
            self_comp = self.with_company(company).sudo()
    
            # 🔹 Determinar mes/año a usar
            if not year or not month:
                config = Config.with_company(company).search([
                    ('company_id', '=', company.id),
                    ('active', '=', True)
                ], limit=1)
    
                if not config or not config.year or not config.month:
                    _logger.warning(f"[ABC][SNAPSHOT][{company.name}] ⚠️ No hay configuración activa válida.")
                    continue
    
                year_t = config.year
                month_t = int(config.month)
            else:
                year_t = int(year)
                month_t = int(month)
    
            last_day = calendar.monthrange(year_t, month_t)[1]
            snapshot_date = date(year_t, month_t, last_day)
    
            _logger.info(f"[ABC][SNAPSHOT][{company.name}] Procesando snapshot de {year_t}-{month_t:02d}")
    
            # 🔹 Buscar o crear batch
            batch = self_comp.env['product.abc.history.batch'].search([
                ('company_id', '=', company.id),
                ('year', '=', year_t),
                ('month', '=', month_t),
            ], limit=1)
    
            if not batch:
                batch = self_comp.env['product.abc.history.batch'].create({
                    'company_id': company.id,
                    'year': year_t,
                    'month': month_t,
                    'snapshot_date': snapshot_date,
                })
                _logger.info(f"[ABC][SNAPSHOT][{company.name}] ➕ Creado nuevo batch {year_t}-{month_t:02d}.")
            else:
                count_old = len(batch.line_ids)
                batch.line_ids.unlink()
                _logger.info(f"[ABC][SNAPSHOT][{company.name}] 🔄 Batch existente {year_t}-{month_t:02d}, {count_old} líneas eliminadas para actualización.")
    
            # 🔹 Obtener productos válidos
            domain = [
                ('type', '!=', 'service'),
                ('company_id', 'in', [False, company.id]),
            ]
            product_ids = self_comp.search(domain).ids
            total = len(product_ids)
            if not total:
                _logger.info(f"[ABC][SNAPSHOT][{company.name}] ⚠️ No hay productos para snapshot {year_t}-{month_t:02d}.")
                continue
    
            # 🔹 Campos a snapshotear
            fields_to_read = [
                'default_code',
                'annual_sales_qty', 'abc_classification'
            ]
    
            total_inserted = 0
            for start in range(0, total, batch_size):
                chunk_ids = product_ids[start:start + batch_size]
                products = self_comp.browse(chunk_ids)
                data = products.read(fields_to_read)
                vals_list = []
    
                for rec in data:
                    vals_list.append({
                        'batch_id': batch.id,
                        'product_id': rec.get('id'),
                        'default_code': rec.get('default_code') or '',
                        'annual_sales_qty': rec.get('annual_sales_qty') or 0.0,
                        'abc_classification': rec.get('abc_classification') or False,
                    })
    
                if vals_list:
                    self_comp.env['product.abc.history.line'].create(vals_list)
                    total_inserted += len(vals_list)
                    self.env.cr.commit()
    
            _logger.info(f"[ABC][SNAPSHOT][{company.name}] ✅ Guardadas {total_inserted} líneas para {year_t}-{month_t:02d}.")
    
        _logger.info("[ABC][SNAPSHOT] ✅ Proceso completado correctamente.")
    


    @api.model
    def cron_run_abc_single_loop(self, batch_size=50, sleep_seconds=20, force=False):
        """
        Un solo disparo: obtiene TODOS los ids de productos (no servicio) y
        ejecuta compute_abc_classification() en lotes de `batch_size`.
        Entre lotes espera `sleep_seconds` segundos. Hace commit por lote.
        """
        today = date.today().day
        if not force and today not in (1, 15):
            _logger.info("[ABC][CRON] No se ejecuta porque no es día 1 ni 15 y no se forzó ejecución.")
            return
    
        companies = self.env['res.company'].search([])
        for company in companies:
            self_comp = self.with_company(company).sudo()
            domain = [
                ('type', '!=', 'service'),
                ('company_id', 'in', [False, company.id]),
            ]
            product_ids = self_comp.search(domain, order='id').ids
            total = len(product_ids)
    
            if not total:
                _logger.info(f"[ABC][CRON][{company.name}] No hay productos para procesar.")
                continue
    
            _logger.info(f"[ABC][CRON][{company.name}] Iniciando procesamiento de {total} productos. Tamaño de lote: {batch_size}")
    
            ejecutados = 0
            lote_num = 0
    
            for start in range(0, total, batch_size):
                stop = min(start + batch_size, total)
                ids_slice = product_ids[start:stop]
                products = self_comp.browse(ids_slice)
    
                lote_num += 1
                _logger.info(f"[ABC][CRON][{company.name}] Ejecutando lote {lote_num}: productos {start + 1}–{stop} de {total}")
                
                products.compute_abc_classification(notify=False)
                ejecutados += len(products)
    
                self.env.cr.commit()
                _logger.info(f"[ABC][CRON][{company.name}] Lote {lote_num} completado. Total ejecutados hasta ahora: {ejecutados}/{total}")
    
                # Espera entre lotes
                if stop < total and sleep_seconds:
                    _logger.info(f"[ABC][CRON][{company.name}] Esperando {sleep_seconds} segundos antes del siguiente lote...")
                    time.sleep(sleep_seconds)
    
            _logger.info(f"[ABC][CRON][{company.name}] ✅ Finalizado. Productos procesados correctamente: {ejecutados}/{total}")

        
    @api.depends('qty_available', 'avg_cost')
    def _compute_costo_total(self):
        for product in self:
            product.costo_total = (product.qty_available or 0.0) * (product.avg_cost or 0.0)

    def _compute_sales_months(self):
        for product in self:
            actual_sales = product._get_sales_by_month_array()
            historical_sales = product._get_historical_sales_by_month_array()

            # Combinar los arrays
            combined_sales = [
                (actual_sales[i] if i < len(actual_sales) else 0.0) +
                (historical_sales[i] if i < len(historical_sales) else 0.0)
                for i in range(12)
            ]

            for i in range(12):
                setattr(product, f'sales_m_{i+1}', combined_sales[i])

    def _compute_months_with_sales_qty(self):
        for product in self:
            actual_sales = product._get_sales_by_month_array()
            historical_sales = product._get_historical_sales_by_month_array()

            combined_sales = [
                (actual_sales[i] if i < len(actual_sales) else 0.0) +
                (historical_sales[i] if i < len(historical_sales) else 0.0)
                for i in range(12)
            ]

            product.months_with_sales_qty = len([v for v in combined_sales if v > 0])

    @api.depends('categ_id')
    def _compute_category_names(self):
        for product in self:
            # Inicializa valores
            product.categ_name = ''
            product.categ_group_name = ''
            product.categ_line_name = ''
            
            if not product.categ_id:
                continue
                
            # Obtener la jerarquía completa
            hierarchy = []
            current = product.categ_id
            while current:
                hierarchy.insert(0, current)
                current = current.parent_id
            
            # Asignar los nombres según el nivel
            if len(hierarchy) >= 1:
                product.categ_line_name = hierarchy[0].name
            if len(hierarchy) >= 2:
                product.categ_group_name = hierarchy[1].name
            if len(hierarchy) >= 3:
                product.categ_name = hierarchy[2].name

    def _get_months_with_sales(self):
        """
        Calcula la cantidad de meses en los que el producto tuvo ventas
        en el último año exacto desde la fecha actual
        """
        self.ensure_one()
        today = fields.Date.today()
        start_date = today - relativedelta(years=1)
        
        # Obtener movimientos de stock de salida (ventas)
        domain = [
            ('product_id', '=', self.id),
            ('date', '>=', start_date),
            ('date', '<=', today),
            ('state', '=', 'done'),
            ('location_dest_id.usage', '=', 'customer'),
            ('company_id', '=', self.env.company.id)
        ]
        
        stock_moves = self.env['stock.move'].search(domain)
        
        # Agregar cada mes en el que hubo ventas a un conjunto
        months_with_sales = set()
        months_with_sales = list(set(stock_moves.mapped(lambda m: m.date.strftime('%Y-%m') if m.date else None)))
        return len(months_with_sales)
        
    def _get_historical_sales_by_month_array(self):
        """
        Devuelve un array de 12 elementos con las ventas históricas por mes,
        usando el mismo rango de fechas definido por la configuración ABC activa.
        """
        self.ensure_one()

        if not self.default_code:
            return [0.0] * 12

        # Buscar configuración activa
        config = self.env['abc.classification.config'].search([
            ('company_id', '=', self.env.company.id),
            ('active', '=', True)
        ], limit=1)

        if not config or not config.month or not config.year:
            return [0.0] * 12  # Configuración incompleta

        # Convertir mes a entero y calcular fecha de corte (último día del mes)
        cutoff_month = int(config.month)
        cutoff_year = config.year
        last_day = calendar.monthrange(cutoff_year, cutoff_month)[1]
        cutoff_date = fields.Date.from_string(f"{cutoff_year}-{cutoff_month:02d}-{last_day}")
        start_date = cutoff_date - relativedelta(months=12)

        # Buscar registros históricos en ese rango
        domain = [
            ('default_code', '=', self.default_code),
            ('date', '>=', start_date),
            ('date', '<=', cutoff_date),
            ('company_id', '=', self.env.company.id)
        ]
        historical_records = self.env['product.sold'].search(domain)

        # Inicializar array de 12 meses
        sales_by_month = [0.0 for _ in range(12)]

        for record in historical_records:
            if not record.date:
                continue

            record_date = record.date
            if start_date <= record_date <= cutoff_date and record.qty_sold_monthly > 0:
                month_diff = (cutoff_date.year - record_date.year) * 12 + (cutoff_date.month - record_date.month)
                index = 11 - month_diff
                if 0 <= index < 12:
                    sales_by_month[index] += record.qty_sold_monthly

        return sales_by_month

        
    def _get_sales_by_month_array(self):
        """
        Devuelve un array con la cantidad vendida (facturada) en cada uno de los últimos 12 meses
        desde la fecha de corte definida en la configuración ABC activa.
        """
        self.ensure_one()

        # Obtener configuración activa
        config = self.env['abc.classification.config'].search([
            ('company_id', '=', self.env.company.id),
            ('active', '=', True)
        ], limit=1)

        if not config or not config.year or not config.month:
            return [0.0 for _ in range(12)]  # Configuración incompleta

        cutoff_month = int(config.month)
        cutoff_year = config.year
        last_day = calendar.monthrange(cutoff_year, cutoff_month)[1]
        cutoff_date = fields.Date.from_string(f"{cutoff_year}-{cutoff_month:02d}-{last_day}")
        start_date = cutoff_date - relativedelta(months=12)

        # Inicializar array de 12 meses (M1 más antigua, M12 el mes de corte)
        sales_by_month = [0.0 for _ in range(12)]

        # Buscar líneas de factura relacionadas al producto
        invoice_lines = self.env['account.move.line'].search([
            ('product_id', '=', self.id),
            ('move_id.move_type', '=', 'out_invoice'),
            ('move_id.state', '=', 'posted'),
            ('move_id.invoice_date', '>=', start_date),
            ('move_id.invoice_date', '<=', cutoff_date),
            ('move_id.company_id', '=', self.env.company.id)
        ])

        for line in invoice_lines:
            invoice_date = line.move_id.invoice_date
            if invoice_date:
                month_diff = (cutoff_date.year - invoice_date.year) * 12 + (cutoff_date.month - invoice_date.month)
                index = 11 - month_diff  # index 11 = mes más reciente
                if 0 <= index < 12:
                    sales_by_month[index] += line.quantity  # Usa `quantity`, no `price_subtotal`

        return sales_by_month

        
    def _get_historical_months_with_sales(self):
        """
        Calcula la cantidad de meses en los que el producto tuvo ventas históricas
        según los datos en product.sold
        """
        self.ensure_one()
        
        # Buscar registros históricos por referencia interna
        if not self.default_code:
            return 0, False
            
        domain = [
            ('default_code', '=', self.default_code)
        ]
        
        # Obtener último año completo de datos
        current_year = fields.Date.today().year
        last_year = str(current_year - 1)
        
        # Restringir a último año completo
        domain.append(('year', '=', last_year))
        domain.append(('company_id', '=', self.env.company.id))
        
        historical_records = self.env['product.sold'].search(domain)
        
        if not historical_records:
            return 0, False
            
        # Contar meses distintos con ventas positivas
        months_with_sales = len(historical_records.filtered(lambda r: r.qty_sold_monthly > 0).mapped('month'))
        
        return months_with_sales, True

    def _is_new_product(self):
        """
        Determina si el producto es nuevo (comprado dentro del rango de los últimos
        3 meses contados desde el mes de corte hasta hoy).
        """
        self.ensure_one()

        if not self.last_purchase_date:
            return False  # Nunca se ha comprado, por tanto no es nuevo

        # Buscar configuración ABC activa
        config = self.env['abc.classification.config'].search([
            ('company_id', '=', self.env.company.id),
            ('active', '=', True)
        ], limit=1)

        if not config or not config.year or not config.month:
            return False  # No se puede evaluar sin configuración válida

        # Calcular fecha de corte: último día del mes anterior definido en config
        cutoff_month = int(config.month)
        cutoff_year = config.year
        import calendar
        last_day = calendar.monthrange(cutoff_year, cutoff_month)[1]
        cutoff_date = fields.Date.from_string(f"{cutoff_year}-{cutoff_month:02d}-{last_day}")

        # Rango desde: 3 meses atrás, primer día
        start_date = (cutoff_date - relativedelta(months=3)).replace(day=1)
        # Rango hasta: hoy
        end_date = fields.Date.today()

        last_purchase_date = self.last_purchase_date.date()

        return start_date <= last_purchase_date <= end_date

    def compute_abc_classification(self, notify=True):
        Config = self.env['abc.classification.config'].sudo()

        # cache por compañía para no hacer search en cada producto
        config_cache = {}

        total = len(self)
        asignados = 0

        for product in self:
            # Empresa a usar: la del producto, y si no tiene, la del entorno
            company = product.company_id or self.env.company

            # Buscar config solo una vez por compañía
            if company.id not in config_cache:
                cfg = Config.with_company(company).search([
                    ('company_id', '=', company.id),
                    ('active', '=', True)
                ], limit=1)
                config_cache[company.id] = cfg or False

                if not cfg:
                    _logger.warning(
                        "[ABC][COMPUTE][%s] No existe configuración ABC activa para esta compañía.",
                        company.display_name
                    )

            config = config_cache[company.id]
            if not config:
                # No hay config ABC para esta compañía → saltamos este producto
                continue

            # ---- LO QUE YA TENÍAS ABAJO LO DEJAMOS IGUAL ----
            product._compute_sales_months()
            product._compute_months_with_sales_qty()
            product._compute_annual_sales_qty()
            product._compute_category_names()
            product._compute_costo_total()

            current_months_with_sales = product._get_months_with_sales()
            historical_months, historical_exists = product._get_historical_months_with_sales()
            months_with_sales = max(current_months_with_sales, historical_months) if historical_exists else current_months_with_sales
            product.has_historical_data = historical_exists

            m = product.months_with_sales_qty or 0
            if m >= config.rating_a:
                letter = 'A'
            elif m >= config.rating_b:
                letter = 'B'
            elif m >= config.rating_c:
                letter = 'C'
            elif m >= config.rating_d:
                letter = 'D'
            else:
                letter = 'E'

            if letter == 'E' and product._is_new_product():
                letter = 'F'

            product.abc_classification = letter
            asignados += 1

        _logger.info(f"[ABC][COMPUTE] Ejecutados (clasificados) = {asignados} de {total}")

        if notify:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Clasificación ABC',
                    'message': f'Clasificación y ventas actualizadas. Ejecutados {asignados}/{total}.',
                    'type': 'success',
                    'sticky': False,
                }
            }



    # def _compute_annual_sales_qty(self):
    #     # Obtener la fecha actual en el contexto del usuario
    #     today = fields.Date.context_today(self)
    #     last_year_date = today - relativedelta(years=1)
        
    #     for product in self:
    #         # Dominio para buscar líneas de pedido de venta
    #         domain = [
    #             ('product_id', 'in', product.product_variant_ids.ids),
    #             ('order_id.state', 'in', ['sale', 'done']),
    #             ('order_id.date_order', '>=', last_year_date),
    #             ('order_id.date_order', '<=', today)
    #         ]
            
    #         # Buscar líneas de pedido de venta
    #         sale_lines = self.env['sale.order.line'].search(domain)
            
    #         # Calcular cantidad total vendida
    #         product.annual_sales_qty = sum(sale_lines.mapped('product_uom_qty'))
    def _compute_annual_sales_qty(self):
        for product in self:
            actual_sales = product._get_sales_by_month_array()
            historical_sales = product._get_historical_sales_by_month_array()
    
            combined_sales = [
                (actual_sales[i] if i < len(actual_sales) else 0.0) +
                (historical_sales[i] if i < len(historical_sales) else 0.0)
                for i in range(12)
            ]
    
            # Asignar ventas por mes a los campos sales_m_1 ... sales_m_12
            for i in range(12):
                setattr(product, f'sales_m_{i+1}', combined_sales[i])
    
            # Asignar la suma total al campo de ventas anuales
            product.annual_sales_qty = sum(combined_sales)


class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    abc_classification = fields.Selection(
        selection=ABC_CLASSIFICATION_SELECTION,
        string='Clasificación ABC',
        compute='compute_abc_classification',
        store=True
    )
    
    annual_sales_qty = fields.Float(
        string='Cantidad Vendida Anual',
    )

    has_historical_data = fields.Boolean(
        string='Incluye Datos Históricos', 
        compute='_compute_has_historical_data',
        store=True
    )
    
    @api.depends('product_variant_ids.abc_classification')
    def compute_abc_classification(self):
        for template in self:
            if template.product_variant_ids:
                template.abc_classification = template.product_variant_ids[0].abc_classification
            else:
                template.abc_classification = False

    @api.depends('product_variant_ids.has_historical_data')
    def _compute_has_historical_data(self):
        for template in self:
            if template.product_variant_ids:
                template.has_historical_data = template.product_variant_ids[0].has_historical_data
            else:
                template.has_historical_data = False
