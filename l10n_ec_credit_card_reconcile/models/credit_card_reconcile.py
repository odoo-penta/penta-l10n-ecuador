
from odoo import models, fields, api
import base64
import xlwt
import xlrd
from datetime import datetime
from io import BytesIO
from odoo.exceptions import UserError

class CreditCardReconcile(models.Model):
    _name = 'credit.card.reconcile'
    _description = 'Conciliación de Tarjetas de Crédito'

    name = fields.Char(
        string='Secuencial',
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: 'New'
    )

    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('in_process', 'En Proceso'),
            ('done', 'Terminado'),
        ],
        string='Estado',
        default='draft'
    )

    fecha_corte = fields.Date(string='Fecha de Corte')
    diario_id = fields.Many2one('account.journal', string='Diario')
    tarjetas_ids = fields.Many2many(
        'account.cards',
        'credit_card_reconcile_account_cards_rel',
        'reconcile_id',
        'card_id',
        string='Tarjetas de Crédito'
    )
    banco_destino_id = fields.Many2one('account.journal', string='Banco Destino')
    cuenta_destino_id = fields.Many2one('account.account', string='Cuenta Destino', compute="_compute_cuenta_destino", readonly=True)
    analitico = fields.Text(string='Analítico')
    responsable_id = fields.Many2one('res.users', string='Responsable')
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )
    
    line_ids = fields.One2many(
        'credit.card.reconcile.line',
        'credit_card_reconcile_id',
        string='Líneas'
    )

    # Relación con las líneas contables (account.move.line)
    move_line_ids = fields.One2many(
        'account.move.line',
        'credit_card_reconcile_id',
        string='Líneas Contables'
    )

    total_move_lines = fields.Integer(
        string="Líneas Contables",
        compute="_compute_total_move_lines"
    )

    @api.depends('banco_destino_id')
    def _compute_cuenta_destino(self):
       
        for rec in self:
            if rec.banco_destino_id:
                print('entrando')
                payment_method_line = rec.banco_destino_id.inbound_payment_method_line_ids.filtered(lambda p: p.payment_account_id)
                rec.cuenta_destino_id = payment_method_line[0].payment_account_id.id if payment_method_line else False
            else:
                rec.cuenta_destino_id = False

    @api.depends('move_line_ids')
    def _compute_total_move_lines(self):
        for rec in self:
            rec.total_move_lines = len(rec.move_line_ids)

    def action_ver_lineas_contables(self):
        """ Retorna la acción para ver las líneas contables asociadas. """
        return {
            'name': 'Líneas Contables',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [('credit_card_reconcile_id', '=', self.id)],
            'context': {'default_credit_card_reconcile_id': self.id},
        }

    @api.model
    def create(self, vals):
        """Asigna secuencia automática y valida que exista."""
        if vals.get('name', 'New') == 'New':
            seq = self.env['ir.sequence'].next_by_code('credit.card.reconcile')
            if not seq:
                raise UserError("❌ No se encontró una secuencia con código 'credit.card.reconcile'.\n\nVe a Ajustes > Técnico > Secuencias y crea una con ese código.")
            vals['name'] = seq
        return super().create(vals)

    # -----------------------------
    # Métodos de los botones
    # -----------------------------


    def action_iniciar(self):
        """Cambia el estado de 'draft' a 'in_process'."""
        self.state = 'in_process'


    def action_buscar_cobros(self):
        """
        Busca los pagos (account.payment) válidos para conciliación:
        - Diario = self.diario_id
        - Fecha entre el primer día del mes y la fecha de corte
        - No hayan sido conciliados ya en otra conciliación
        Crea líneas por cada uno y muestra info si se excluyeron pagos ya usados.
        """
        self.ensure_one()

        if not self.fecha_corte or not self.diario_id:
            raise UserError("Debe seleccionar una fecha de corte y un diario.")

        date_corte = fields.Date.from_string(self.fecha_corte)
        start_date = date_corte.replace(day=1)

        # Buscar líneas ya conciliadas en el rango actual
        lineas_conciliadas = self.env['credit.card.reconcile.line'].search([
            ('credit_card_reconcile_id', '!=', False),
            ('move_line_id.move_id.date', '>=', start_date),
            ('move_line_id.move_id.date', '<=', date_corte),
            ('move_line_id.move_id.journal_id', '=', self.diario_id.id),
        ])

        pagos_conciliados_ids = lineas_conciliadas.mapped('move_line_id.move_id.id')

        # Armar dominio de búsqueda
        domain = [
            ('journal_id', '=', self.diario_id.id),
            ('date', '>=', start_date),
            ('date', '<=', date_corte),
            ('move_id', 'not in', pagos_conciliados_ids),
        ]

        # Si se seleccionaron tarjetas, buscar los códigos del selection (used_card)
        if self.tarjetas_ids:
            # Buscar en el mapa los selection_code asociados a estas tarjetas
            codigos = self.env['account.card.map'].search([
                ('card_id', 'in', self.tarjetas_ids.ids),
            ]).mapped('selection_code')

            if codigos:
                domain.append(('used_card', 'in', codigos))
            
            
        payments = self.env['account.payment'].search(domain)

        for pay in payments:
            move_lines = self.env['account.move.line'].search([
                ('move_id', '=', pay.move_id.id),
                ('account_id', '=', self.diario_id.default_account_id.id),
            ])
            for line in move_lines:
                self.env['credit.card.reconcile.line'].create({
                    'credit_card_reconcile_id': self.id,
                    'move_line_id': line.id,
                    'lot_number': pay.x_studio_lote,
                    'credit_card_voucher_number': pay.reference_number,
                    'credit_card_type_id': pay.credit_card_type_id.id,
                    'paid_amount': pay.amount,
                    'payment_id': pay.id, 
                    'payment_date': False,
                    'total_deposit': 0.0,
                    'income_amount': 0.0,
                    'vat_amount': 0.0,
                    'commission': 0.0,
                    'bank_voucher_number': False,
                    'withhold_sequential': False,
                    'withhold_state': False,
                })

        # Mostrar mensaje si hubo excluidos
        if lineas_conciliadas:
            mensaje = "Los siguientes pagos fueron excluidos por ya estar conciliados:<br/>"
            for linea in lineas_conciliadas:
                move = linea.move_line_id.move_id
                mensaje += f"- Pago: {move.name or 'N/A'}, Fecha: {move.date}, Conciliación: {linea.credit_card_reconcile_id.name}<br/>"

            return True  # Si no hubo conciliados previos, finaliza normalmente


    def action_exportar(self):
            """
            Exporta las 'line_ids' a un Excel .xls y abre un wizard
            para que el usuario pueda descargar el archivo.
            """
            
            # 1) Crear un workbook en memoria con xlwt
            wb = xlwt.Workbook(encoding='utf-8')
            ws = wb.add_sheet('Movements')

            # 2) Declarar estilos para celeste y amarillo
            style_celeste = xlwt.easyxf('pattern: pattern solid, fore_colour pale_blue;')
            style_amarillo = xlwt.easyxf('pattern: pattern solid, fore_colour light_yellow;')

            # 3) Definir los encabezados según tu formato
            headers = [
                'IDENTIFICADOR DEL APUNTE',  # move_line_id
                '#Lote',
                '#Voucher',
                'TARJETA DE CRÉDITO',
                'VALOR PAGADO',
                'FECHA DE PAGO',
                'VALOR DEPÓSITO TOTAL',
                'RETENCIÓN RENTA',
                'RETENCIÓN IVA',
                'COMISIÓN',
                'NRO. COMPROBANTE BANCO',
                'SECUENCIAL RETENCIÓN',
                'SECUENCIAL FACTURA COMISIÓN',
            ]

            # 4) Escribir los encabezados (fila 0) con estilos
            for col, header in enumerate(headers):
                # Si la columna está entre 0 y 4 inclusive => celeste, sino => amarillo
                if col <= 4:
                    ws.write(0, col, header, style_celeste)
                else:
                    ws.write(0, col, header, style_amarillo)

            # 5) Rellenar filas con datos de line_ids
            row = 1
            for line in self.line_ids:
                # Definimos los valores de cada columna
                row_values = [
                    line.move_line_id.id if line.move_line_id else '',
                    line.lot_number or '',
                    line.credit_card_voucher_number or '',
                    line.credit_card_type_id.name if line.credit_card_type_id else '',
                    line.paid_amount or 0.0,
                    fields.Date.to_string(line.payment_date) if line.payment_date else '',
                    line.total_deposit or 0.0,
                    line.income_amount or 0.0,
                    line.vat_amount or 0.0,
                    line.commission or 0.0,
                    line.bank_voucher_number or '',
                    line.withhold_sequential or '',
                    line.invoice_supplier_sequential or '',
                ]

                # Escribir cada valor en su columna
                for col, val in enumerate(row_values):
                    # Estilo: primeras 5 columnas => celeste, las demás => amarillo
                    if col <= 4:
                        ws.write(row, col, val, style_celeste)
                    else:
                        ws.write(row, col, val, style_amarillo)
                row += 1

            # 6) Guardar el workbook en un buffer de memoria
            fp = BytesIO()
            wb.save(fp)
            fp.seek(0)
            file_data = fp.read()
            fp.close()

            # 7) Codificar en Base64 para guardarlo en un wizard
            out_file = base64.b64encode(file_data)

            # 8) Crear wizard (TransientModel) para mostrar el archivo
            wizard_id = self.env['export.movements.wizard'].create({
                'file_data': out_file,
                'file_name': 'movements.xls',
            })

            # 9) Retornar action para abrir ese wizard en pantalla
            return {
                'name': "Descargar Excel",
                'type': 'ir.actions.act_window',
                'res_model': 'export.movements.wizard',
                'view_mode': 'form',
                'res_id': wizard_id.id,
                'target': 'new',
            }


    def action_importar(self):
        """
        Crea y abre el wizard para subir el archivo y ejecutar la importación.
        """
        self.ensure_one()
        wizard = self.env['import.movements.wizard'].create({
            'credit_card_reconcile_id': self.id,
        })
        return {
            'name': "Importar Movimientos",
            'type': 'ir.actions.act_window',
            'res_model': 'import.movements.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_buscar_retenciones(self):
        """
        Busca retenciones (code 07) y facturas proveedor (code 01) por secuencial y partner.
        """
        self.ensure_one()

        partner = self.diario_id.reference_contact_id
        if not partner:
            print("El diario no tiene un contacto de referencia asignado.")
            return

        doc_type_ret = self.env['l10n_latam.document.type'].search([('code', '=', '07')], limit=1)
        doc_type_inv = self.env['l10n_latam.document.type'].search([('code', '=', '01')], limit=1)

        for line in self.line_ids:

            # Buscar RETENCIONES
            if line.withhold_sequential:
                sec_ret = line.withhold_sequential.strip() if line.withhold_sequential else None

                move_ret = self.env['account.move'].search([
                    ('l10n_latam_document_type_id', '=', doc_type_ret.id),
                    ('ref', '=', sec_ret),
                    ('partner_id', '=', partner.id),
                    ('state', '=', 'posted'),
                ], limit=1)

                if move_ret and move_ret.name:
                    line.credit_card_withhold_id = move_ret.id
                    line.withhold_state = 'done'
                else:
                    line.withhold_state = 'pending'

            # # Buscar FACTURAS DE PROVEEDOR
            # if line.invoice_supplier_sequential:
            #     sec_ret = line.invoice_supplier_sequential.strip() if line.invoice_supplier_sequential else None

            #     move_inv = self.env['account.move'].search([
            #         ('l10n_latam_document_type_id', '=', doc_type_inv.id),
            #         ('ref', '=', sec_inv),
            #         ('partner_id', '=', partner.id),
            #         ('state', '=', 'posted'),
            #     ], limit=1)

            #     if move_inv and move_inv.name:
            #         line.invoice_supplier_id = move_inv.id
            #         line.invoice_supplier_state = 'done'
            #     else:
            #         line.invoice_supplier_state = 'pending'

    def action_crear_asientos(self):
        """
        Crea un asiento contable por cada línea válida:
        - El asiento tendrá:
            - Crédito: cuenta del pago
            - Débitos:
                * Comisión (cuenta del diario) con nombre del banco
                * Retenciones (Renta + IVA)
                * Depósito (cuenta del método de pago 'Liquidación de TC')
        - La referencia será el número de factura del proveedor.
        """
        self.ensure_one()

        # 1. Filtrar líneas válidas
        valid_lines = []
        invalid_info = []  # [(line, reason), ...]
        
        TOL = 0.01
        for line in self.line_ids:
            # Regla 1: suma de detalles = total pagado
            suma_detalles = (line.total_deposit or 0.0) + (line.income_amount or 0.0) \
                            + (line.vat_amount or 0.0) + (line.commission or 0.0)
            if abs(round(suma_detalles, 2) - round(line.paid_amount or 0.0, 2)) >= TOL:
                invalid_info.append((
                    line,
                    f"Suma de detalles ({suma_detalles:.2f}) != Total pagado ({(line.paid_amount or 0.0):.2f})"
                ))
                continue
        
            # Regla 2: si hay montos de retención, la retención debe estar validada
            if (line.income_amount or 0.0) or (line.vat_amount or 0.0):
                if line.withhold_state != 'done':
                    invalid_info.append((line, "Retención pendiente (withhold_state != 'done')"))
                    continue
                # Y además debe existir vínculo (move) o al menos secuencial
                if not line.credit_card_withhold_id and not (line.withhold_sequential or '').strip():
                    invalid_info.append((line, "Falta enlazar retención o indicar secuencial de retención"))
                    continue
        
            # Si pasó todo:
            valid_lines.append(line)
        
        # Si hay inválidas, bloquear con detalle
        if invalid_info:
            # Armar un mensaje legible por línea
            # Identificamos por: Pago (move), Voucher, Lote y razón
            detalles = []
            for ln, reason in invalid_info:
                move_name = ln.move_line_id.move_id.name or 'N/A'
                voucher = ln.credit_card_voucher_number or 'N/A'
                lote = ln.lot_number or 'N/A'
                detalles.append(f"- Pago: {move_name} | Voucher: {voucher} | Lote: {lote} -> {reason}")
            msg = "Hay líneas de conciliación no válidas. Debe corregirlas o eliminarlas antes de generar asientos:\n\n" + "\n".join(detalles)
            raise UserError(msg)
        
        # Si no hay válidas (y tampoco inválidas) => nada que hacer
        if not valid_lines:
            raise UserError("No hay líneas válidas para generar asientos contables.")
        # 2. Validar retenciones
        withhold_map = {}
        for line in valid_lines:
            if line.credit_card_withhold_id:
                wid = line.credit_card_withhold_id.id
                if wid not in withhold_map:
                    withhold_map[wid] = {'renta': 0.0, 'iva': 0.0, 'obj': line.credit_card_withhold_id}
                withhold_map[wid]['renta'] += line.income_amount or 0.0
                withhold_map[wid]['iva'] += line.vat_amount or 0.0

        for data in withhold_map.values():
            move = data['obj']
            impuestos_renta = 0.0
            impuestos_iva = 0.0
            for tax_line in move.line_ids.filtered(lambda l: l.tax_ids):
                for tax in tax_line.tax_ids:
                    group = tax.tax_group_id
                    if group.tax_type == 'renta':
                        impuestos_renta += tax_line.l10n_ec_withhold_tax_amount 
                    elif group.tax_type == 'iva':
                        impuestos_iva += tax_line.l10n_ec_withhold_tax_amount

            diff_renta = round(impuestos_renta, 2) - round(data['renta'], 2)
            diff_iva = round(impuestos_iva, 2) - round(data['iva'], 2)

            if abs(diff_renta) >= 0.01:
                raise UserError(
                    f"Retención Renta en {move.name} ({impuestos_renta:.2f}) no coincide con líneas ({data['renta']:.2f})"
                )
            if abs(diff_iva) >= 0.01:
                raise UserError(
                    f"Retención IVA en {move.name} ({impuestos_iva:.2f}) no coincide con líneas ({data['iva']:.2f})"
                )

        # 3. Cuentas necesarias
        if not self.diario_id.account_commission:
            raise UserError("El diario no tiene configurada la cuenta de comisión.")
        if not self.diario_id.account_withhold:
            raise UserError("El diario no tiene configurada la cuenta de retenciones.")

        account_commission_id = self.diario_id.account_commission.id
        retention_account_id = self.diario_id.account_withhold.id

        # 4. Obtener cuenta de depósito desde método 'Liquidación de TC'
        payment_account = self._get_liquidacion_tc_account()
        if not payment_account:
            raise UserError("No se encontró un método 'Liquidación de TC' en el banco destino.")
        payment_account_id = payment_account.id

        # 5. Crear asiento por cada línea
        for line in valid_lines:
            move_line_vals = []

            # Crédito - cuenta original del pago
            move_line_vals.append((0, 0, {
                'account_id': line.move_line_id.account_id.id,
                'name': f"Línea Conciliación: {line.credit_card_voucher_number or ''}",
                'credit': line.paid_amount,
                'debit': 0.0,
                'credit_card_reconcile_id': self.id,
                'partner_id': line.move_line_id.partner_id.id,
            }))

            # Débito - Comisión
            if line.commission:
                move_line_vals.append((0, 0, {
                    'account_id': account_commission_id,
                    'name': 'Comisión: ' + (line.invoice_supplier_sequential or ''),
                    'debit': line.commission,
                    'credit': 0.0,
                    'credit_card_reconcile_id': self.id,
                    'partner_id': self.diario_id.reference_contact_id.id,
                }))

            # Débito - Retenciones
            total_ret = (line.income_amount or 0.0) + (line.vat_amount or 0.0)
            if total_ret:
                move_line_vals.append((0, 0, {
                    'account_id': retention_account_id,
                    'name': "Retenciones Renta + IVA: " + (line.withhold_sequential or ''),
                    'debit': total_ret,
                    'credit': 0.0,
                    'credit_card_reconcile_id': self.id,
                    'partner_id': self.diario_id.reference_contact_id.id,
                }))

            # Débito - Depósito
            if line.total_deposit:
                move_line_vals.append((0, 0, {
                    'account_id': payment_account_id,
                    'name': "Depósito",
                    'debit': line.total_deposit,
                    'credit': 0.0,
                    'credit_card_reconcile_id': self.id,
                    'partner_id': self.banco_destino_id.reference_contact_id.id,
                }))

            # Crear asiento
            move_vals = {
                'journal_id': self.diario_id.id,
                'date': fields.Date.today(),
                'line_ids': move_line_vals,
                'ref': line.bank_voucher_number or '',
            }

            move = self.env['account.move'].create(move_vals)
            move.action_post()

            # Relacionar líneas al registro
            self.move_line_ids += move.line_ids

        # Confirmación visual
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Asientos contables generados",
                'message': f"Se generaron {len(valid_lines)} asientos contables.",
                'type': 'success',
                'sticky': False,
            }
        }

    def action_terminar(self):
        # Lógica para "Terminar"
        self.state = 'done'

    def action_set_draft(self):
        # Lógica para regresar a borrador
        self.state = 'draft'
        
    def _get_liquidacion_tc_account(self):
        """
        Devuelve el `payment_account_id` de la línea de método de pago
        entrante cuyo Nombre contenga 'liquidacion de tc' dentro del
        banco destino.
        """
        self.ensure_one()
        journal = self.banco_destino_id
        if not journal:
            return False

        # 1) Coincide con el Nombre de la línea (columna "Nombre" en el diario)
        line = journal.inbound_payment_method_line_ids.filtered(
            lambda l: 'liquidacion de tc' in (l.name or '').lower()
        )
        # 2) Fallback por nombre del método (por si alguien lo puso ahí)
        if not line:
            line = journal.inbound_payment_method_line_ids.filtered(
                lambda l: 'liquidacion de tc' in (l.payment_method_id.name or '').lower()
            )

        return (line[:1].payment_account_id) or False




class ExportMovementsWizard(models.TransientModel):
    _name = 'export.movements.wizard'
    _description = 'Wizard para Exportar Movimientos'

    file_data = fields.Binary('Archivo', readonly=True)
    file_name = fields.Char('Nombre Archivo', readonly=True)

    def action_download_file(self):
        """
        Retorna una acción para descargar el archivo desde este wizard.
        """
        return {
            'type': 'ir.actions.act_url',
            'url': 'web/content/?model=export.movements.wizard&id=%s&field=file_data&filename_field=file_name&download=true' % (self.id),
            'target': 'self',
        }
