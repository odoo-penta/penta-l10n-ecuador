
from datetime import timedelta
from odoo import models, fields, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    bank_forecast_date = fields.Date(
        string='Fecha prevista del banco',
        compute='_compute_bank_forecast_date',
    )

    @api.depends()
    def _compute_bank_forecast_date(self):
        for record in self:
            record.bank_forecast_date = False  # Default

            if not record.x_studio_tarjeta or not record.journal_id or not record.x_studio_tipo_de_cobro or record.x_studio_nmero_de_meses is None:
                continue

            # Buscar el método de pago POS que coincida por nombre
            pos_payment_method = self.env['pos.payment.method'].search([
                ('name', '=', record.x_studio_tarjeta)
            ], limit=1)

            if not pos_payment_method:
                continue

            # Buscar la configuración completa que coincida
            config = self.env['penta.bank.days'].search([
                ('pos_payment_method_id', '=', pos_payment_method.id),
                ('journal_id', '=', record.journal_id.id),
                ('payment_type', '=', record.x_studio_tipo_de_cobro),
                ('number_of_months', '=', str(record.x_studio_nmero_de_meses))  # ¡Ojo! number_of_months es SELECTION (string)
            ], limit=1)

            if not config:

                continue

            if record.date and config.number_of_days:
                record.bank_forecast_date = record.date + timedelta(days=config.number_of_days)


