# -*- coding: utf-8 -*-
import base64
import xlrd
from odoo import models, fields, api
from odoo.exceptions import UserError

class ImportMovementsWizard(models.TransientModel):
    _name = 'import.movements.wizard'
    _description = 'Wizard para Importar Movements desde Excel'

    credit_card_reconcile_id = fields.Many2one(
        'credit.card.reconcile',
        required=True,
        string="Conciliación de Tarjetas"
    )
    import_file = fields.Binary(
        string='Archivo para Importar',
        required=True
    )
    file_name = fields.Char(string='Nombre de Archivo')

    def action_importar(self):
        """
        Método que se dispara al hacer clic en el botón de 'Importar' en el wizard.
        Lee el Excel y actualiza las líneas de 'credit.card.reconcile.line'
        basándose en la columna 'IDENTIFICADOR DEL APUNTE' (move_line_id).
        """
        self.ensure_one()
        if not self.import_file:
            raise UserError("No se ha cargado ningún archivo para importar.")

        # 1) Decodificar el archivo en memoria
        file_data = base64.b64decode(self.import_file)
        try:
            book = xlrd.open_workbook(file_contents=file_data)
        except Exception as e:
            raise UserError("Error al leer el archivo: %s" % e)

        sheet = book.sheet_by_index(0)

        # 2) Leer encabezados para guiarte (opcional) o asumir orden fijo
        # Asumamos que la fila 0 son encabezados y que no cambia el orden,
        # tal como en el método de export
        # Orden esperado de columnas:
        #  0) IDENTIFICADOR DEL APUNTE (move_line_id)
        #  1) #Lote
        #  2) #Voucher
        #  3) TARJETA DE CRÉDITO
        #  4) VALOR PAGADO
        #  5) FECHA DE PAGO
        #  6) VALOR DEPÓSITO TOTAL
        #  7) RETENCIÓN RENTA
        #  8) RETENCIÓN IVA
        #  9) COMISIÓN
        # 10) NRO. COMPROBANTE BANCO
        # 11) SECUENCIAL RETENCIÓN

        # 3) Iterar desde la fila 1 (datos) hasta nrows
        for rx in range(1, sheet.nrows):
            row = sheet.row(rx)

            # Leer el IDENTIFICADOR DEL APUNTE
            move_line_id_value = row[0].value
            if not move_line_id_value:
                # Si no hay identificador, saltar
                continue

            # Buscar la línea que coincida con credit_card_reconcile_id + move_line_id
            line = self.env['credit.card.reconcile.line'].search([
                ('credit_card_reconcile_id', '=', self.credit_card_reconcile_id.id),
                ('move_line_id', '=', int(move_line_id_value)),  # forzamos a entero si procede
            ], limit=1)

            if not line:
                # Si no encuentra la línea, podría continuar o mostrar un warning/log
                continue

            # Extraer los demás campos a actualizar
            # Col 5 => FECHA DE PAGO
            payment_date = False
            cell_payment_date = row[5]
            if cell_payment_date.ctype == xlrd.XL_CELL_DATE:
                # Si es fecha nativa de Excel, convertir
                date_tuple = xlrd.xldate_as_tuple(cell_payment_date.value, book.datemode)
                payment_date = fields.Date.to_string(
                    f"{date_tuple[0]:04d}-{date_tuple[1]:02d}-{date_tuple[2]:02d}"
                )
            else:
                # Podría venir como string
                if cell_payment_date.value:
                    payment_date_str = str(cell_payment_date.value).strip()
                    # Ajusta al formato que uses (ej: 'YYYY-MM-DD')
                    payment_date = payment_date_str

            # Col 6 => VALOR DEPÓSITO TOTAL
            total_deposit_val = row[6].value or 0.0
            # Col 7 => RETENCIÓN RENTA
            rent_retention_val = row[7].value or 0.0
            # Col 8 => RETENCIÓN IVA
            vat_retention_val = row[8].value or 0.0
            # Col 9 => COMISIÓN
            commission_val = row[9].value or 0.0
            # Col 10 => NRO. COMPROBANTE BANCO
            bank_voucher_val = row[10].value or ''
            # Col 11 => SECUENCIAL RETENCIÓN
            withhold_seq_val = row[11].value or ''
            # Col 12 => SECUENCIAL FACTURA COMISIÓN (si existe)
            invoice_supplier_seq_val = row[12].value or ''
            
            # 4) Actualizar la línea
            line.write({
                'payment_date': payment_date,
                'total_deposit': total_deposit_val,
                'income_amount': rent_retention_val,
                'vat_amount': vat_retention_val,
                'commission': commission_val,
                'bank_voucher_number': bank_voucher_val,
                'withhold_sequential': withhold_seq_val,
                'invoice_supplier_sequential': invoice_supplier_seq_val,
            })

        return {
            'effect': {
                'fadeout': 'slow',
                'message': "Importación completada con éxito.",
                'type': 'rainbow_man',
            }
        }
