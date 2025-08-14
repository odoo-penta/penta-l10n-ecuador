from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class CobrosPorVentas(models.Model):
    _name = 'cobros.por.ventas'
    _description = 'Reporte de Cobros por Ventas'
    _auto = False

    x_date = fields.Date(string='Fecha')
    x_journal = fields.Char(string='Diario')
    x_move_name = fields.Char(string='Nombre del Asiento')
    x_reference = fields.Char(string='Referencia')
    x_account = fields.Char(string='Cuenta')
    x_partner_name = fields.Char(string='Cliente')
    x_tag = fields.Char(string='Etiqueta')
    x_debit = fields.Float(string='Débito')
    x_credit = fields.Float(string='Crédito')
    x_account_type = fields.Char(string='Tipo de Cuenta')
    x_payment_type = fields.Char(string='Tipo de Pago')

    def init(self):
        self.env.cr.execute("""
CREATE OR REPLACE VIEW cobros_por_ventas AS (
    SELECT
        row_number() OVER () as id,
        am.date as x_date,
        COALESCE((jo.name ->> 'es_EC'), '')::varchar as x_journal,
        am.name as x_move_name,
        am.ref as x_reference,
        COALESCE((ac.name ->> 'es_EC'), '')::varchar as x_account,
        cli.name as x_partner_name,
        aml.name as x_tag,
        aml.debit as x_debit,
        aml.credit as x_credit,
        ac.account_type as x_account_type,
        ap.payment_type as x_payment_type
    FROM account_move am
    LEFT JOIN account_payment ap ON am.id = ap.move_id
    JOIN account_journal jo ON am.journal_id = jo.id
    JOIN account_move_line aml ON am.id = aml.move_id
    JOIN res_partner cli ON aml.partner_id = cli.id
    JOIN account_account ac ON aml.account_id = ac.id
    WHERE (
        (jo.type = 'cash' AND ac.account_type = 'asset_cash')
        OR (
            jo.type = 'bank'
            AND ac.account_type IN ('asset_current', 'liability_credit_card')
            AND COALESCE((ac.name ->> 'es_EC'), '')::varchar NOT LIKE '%Transferencia de liquidez%'
        )
    )
    AND am.state = 'posted'
    AND aml.debit != 0
    AND COALESCE((ac.name ->> 'es_EC'), '')::varchar NOT LIKE '%Pagos%'
    ORDER BY am.date ASC
)
        """)

    def _get_report_base_filename(self):
        return 'Cobros_por_Ventas'

    @api.model
    def read(self, fields=None, load='_classic_read'):
        result = super(CobrosPorVentas, self).read(fields=fields, load=load)
        for record in result:
            if 'x_journal' in record and record['x_journal']:
                record['x_journal'] = record['x_journal'].strip('"').replace('\"', '')
            if 'x_account' in record and record['x_account']:
                record['x_account'] = record['x_account'].strip('"').replace('\"', '')
        return result  # Corrección: eliminado la coma extra