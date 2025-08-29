from odoo import models, fields, api

class PagosPorCompras(models.Model):
    _name = 'pagos.por.compras'
    _description = 'Reporte de Pagos por Compras'
    _auto = False

    x_date = fields.Date(string='Fecha')
    x_journal = fields.Many2one('account.journal', string='Diario', readonly=True)
    x_move_name = fields.Many2one('account.move', string='Nombre del Asiento', readonly=True)
    x_reference = fields.Char(string='Referencia')
    x_account = fields.Many2one('account.account', string='Cuenta', readonly=True)
    x_partner_name = fields.Many2one('res.partner', string='Proveedor', readonly=True)
    x_tag = fields.Char(string='Etiqueta')
    x_credit = fields.Float(string='Crédito')
    x_debit = fields.Float(string='Débito')
    x_account_type = fields.Char(string='Tipo de Cuenta')
    x_payment_type = fields.Char(string='Tipo de Pago')

    def init(self):
        # Eliminar la vista existente si existe
        self.env.cr.execute("DROP VIEW IF EXISTS pagos_por_compras")
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pagos_por_compras AS (
                SELECT
                    row_number() OVER () as id,
                    am.date as x_date,
                    jo.id as x_journal,  -- ID del diario
                    am.id as x_move_name,  -- ID del asiento
                    am.ref as x_reference,
                    ac.id as x_account,  -- ID de la cuenta
                    cli.id as x_partner_name,  -- ID del proveedor
                    aml.name as x_tag,
                    aml.credit as x_credit,
                    aml.debit as x_debit,
                    ac.account_type as x_account_type,
                    ap.payment_type as x_payment_type
                FROM account_move am
                LEFT JOIN account_payment ap ON am.id = ap.move_id
                JOIN account_journal jo ON am.journal_id = jo.id
                JOIN account_move_line aml ON am.id = aml.move_id
                JOIN res_partner cli ON aml.partner_id = cli.id
                JOIN account_account ac ON aml.account_id = ac.id
                WHERE (
                    (jo.type = 'cash' AND ac.account_type = 'liability_payable')
                    OR (
                        jo.type = 'bank'
                        AND ac.account_type = 'liability_payable'
                        AND jsonb_pretty(ac.name -> 'es_EC')::varchar NOT LIKE '%Transferencia de liquidez%'
                    )
                )
                AND am.state = 'posted'
                AND aml.credit != 0
                AND jsonb_pretty(ac.name -> 'es_EC')::varchar NOT LIKE '%Anticipos%'
                ORDER BY am.date ASC
            )
        """)