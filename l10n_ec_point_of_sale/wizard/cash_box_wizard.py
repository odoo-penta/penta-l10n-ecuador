# -*- coding: utf-8 -*-
# Part of PentaLab. See LICENSE file for full copyright and licensing details.
# © 2025 PentaLab
# License Odoo Proprietary License v1.0 (https://www.odoo.com/documentation/user/16.0/legal/licenses/licenses.html#odoo-proprietary-license)
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round


class CashBoxBaseWizard(models.AbstractModel):
    _name = 'cash.box.base.wizard'
    _description = 'Base Cash Box Wizard'
    _abstract = True

    cash_id = fields.Many2one('cash.box', required=True, string="Cash Box")
    session_id = fields.Many2one('cash.box.session', string="Session")
    currency_id = fields.Many2one('res.currency', related='cash_id.currency_id', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    opening_note = fields.Text()
    closing_note = fields.Text()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        cash_id = self.env.context.get('default_cash_id')
        if not cash_id and self.env.context.get('active_id'):
            session = self.env['cash.box.session'].browse(self.env.context.get('active_id'))
            if session.exists():
                cash_id = session.cash_id.id
        if cash_id:
            cash = self.env['cash.box'].browse(cash_id)
            res['cash_id'] = cash.id
        return res

class CashBoxCoinLineWizard(models.TransientModel):
    _name = 'cash.box.coin.line.wizard'
    _description = 'Coin Line for Initial Balance Wizard'

    wizard_id = fields.Many2one('cash.box.coin.wizard', required=True, ondelete='cascade')
    coin_id = fields.Many2one('cash.box.coin', required=True, readonly=True)
    value = fields.Float(related='coin_id.value', readonly=True)
    quantity = fields.Integer(default=0)

class CashBoxCoinWizard(models.TransientModel):
    _name = 'cash.box.coin.wizard'
    _description = 'Select Coins for Balance'
    
    opened_wizard_id = fields.Many2one('cash.box.open.wizard', ondelete='cascade')
    closed_wizard_id = fields.Many2one('cash.box.closed.wizard', ondelete='cascade')
    coin_line_ids = fields.One2many('cash.box.coin.line.wizard', 'wizard_id', string="Coins")

    def action_confirm_coins(self):
        total = sum(line.value * line.quantity for line in self.coin_line_ids)
        # Construcción del detalle
        coin_lines = []
        for line in self.coin_line_ids:
            if line.quantity > 0:
                coin_lines.append(f"{line.coin_id.name} x {line.quantity}")
        detail_text = "\n".join(coin_lines)
        detail_text += f"\nTotal: ${total:.2f}"
        ctx = self.env.context
        if ctx.get('default_opened_wizard_id'):
            wizard = self.env['cash.box.open.wizard'].browse(ctx['default_opened_wizard_id'])
            wizard.initial_balance = total
            wizard.opening_note = detail_text
            return {
                'name': _('Open Cash Box'),
                'type': 'ir.actions.act_window',
                'res_model': 'cash.box.open.wizard',
                'view_mode': 'form',
                'res_id': wizard.id,
                'target': 'new',
            }
        elif ctx.get('default_closed_wizard_id'):
            wizard = self.env['cash.box.closed.wizard'].browse(ctx['default_closed_wizard_id'])
            wizard.final_balance = total
            wizard.closing_note = detail_text
            return {
                'name': _('Closed Cash Box'),
                'type': 'ir.actions.act_window',
                'res_model': 'cash.box.closed.wizard',
                'view_mode': 'form',
                'res_id': wizard.id,
                'target': 'new',
            }

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        lines = []
        for coin in self.env['cash.box.coin'].search([], order='value asc'):
            lines.append((0, 0, {'wizard_id': self.env.context.get('active_id', False),  'coin_id': coin}))
        res['coin_line_ids'] = lines
        return res
    
class CashBoxOpenWizard(models.TransientModel):
    _name = 'cash.box.open.wizard'
    _inherit = 'cash.box.base.wizard'
    _description = 'Open Cash Box Wizard'

    initial_balance = fields.Monetary(string="Initial Balance", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        cash = self.env['cash.box'].browse(res.get('cash_id'))
        last_session = self.env['cash.box.session'].search(
            [('cash_id', '=', cash.id), ('state', '=', 'closed')],
            order="closing_date desc", limit=1
        )
        last_balance = last_session.closing_balance if last_session else 0.0
        res.update({
            'initial_balance': last_balance,
        })
        return res
    
    def action_open_coin_wizard(self):
        # Crear el wizard con líneas
        wizard = self.env['cash.box.coin.wizard'].create({
            'opened_wizard_id': self.id,
            'coin_line_ids': [
                (0, 0, {
                    'coin_id': coin.id,
                    'quantity': 0,
                }) for coin in self.env['cash.box.coin'].search([('currency_id', '=', self.currency_id.id)], order='value asc')
            ]
        })
        return {
            'name': _('Select Coins'),
            'type': 'ir.actions.act_window',
            'res_model': 'cash.box.coin.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_confirm_open(self):
        self.ensure_one()
        # validamos estado
        if self.cash_id.state == 'open':
            raise UserError(_("The cash box is already open."))
        # proceso de apertura
        session = self.cash_id.open_cash(self.initial_balance)
        session.opening_note = self.opening_note
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cash.box.session',
            'res_id': session.id,
            'view_mode': 'form',
            'target': 'current',
        }
        
class CashBoxClosedWizard(models.TransientModel):
    _name = 'cash.box.closed.wizard'
    _inherit = 'cash.box.base.wizard'
    _description = 'Closed Cash Box Wizard'

    final_balance = fields.Monetary(string="Final Balance", required=True)
    suggested_balance = fields.Monetary(readonly=True)
    exceeds_limit = fields.Boolean(string="Exceeds Limit", compute="_compute_exceeds_limit")
    
    @api.depends('final_balance')
    def _compute_exceeds_limit(self):
        limit_amount = float(self.env['ir.config_parameter'].sudo().get_param('l10n_ec_point_of_sale.cash_imbalance_limit'))
        for record in self:
            record.exceeds_limit = False
            if limit_amount > 0.0:
                diff = record.final_balance - record.suggested_balance
                if (diff > 0 and diff >= limit_amount) or (diff < 0 and abs(diff) >= limit_amount):
                    record.exceeds_limit = True

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        cash_id = self.env.context.get('default_cash_id', False)
        if cash_id:
            cash = self.env['cash.box'].browse(cash_id)
            movement_ids = cash.current_session_id.movement_ids
            import pdb;pdb.set_trace()
            summary = self._get_payment_summary(movement_ids=movement_ids)
            total_cash = sum(item['cash'] for item in summary.values())
            total_cash += cash.current_session_id.initial_balance
            res['suggested_balance'] = total_cash
        return res
    
    def action_close_coin_wizard(self):
        # Crear el wizard con líneas
        wizard = self.env['cash.box.coin.wizard'].create({
            'closed_wizard_id': self.id,
            'coin_line_ids': [
                (0, 0, {
                    'coin_id': coin.id,
                    'quantity': 0,
                }) for coin in self.env['cash.box.coin'].search([('currency_id', '=', self.currency_id.id)], order='value asc')
            ]
        })
        return {
            'name': _('Select Coins'),
            'type': 'ir.actions.act_window',
            'res_model': 'cash.box.coin.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
        
    @api.onchange('final_balance')
    def _oncahnge_final_balance(self):
        self.closing_note = ''
        
    def applied_diff_closing_balance(self):
        self.ensure_one()
        move_obj = self.env['account.move']
        journal = self.cash_id.close_journal_id
        # Calculo de diferencia
        diff = float_round(self.final_balance - self.suggested_balance, precision_digits=2)
        account_cash = self.cash_id.close_account_id
        if not account_cash:
            raise UserError(_("The journal must have a default account."))
        move_vals = {
            'ref': _('Cash closing adjustment'),
            'journal_id': journal.id,
            'date': fields.Date.context_today(self),
            'line_ids': [],
        }
        if diff > 0:
            # Hay más efectivo del esperado → GANANCIA
            gain_account = self.cash_id.gain_account_id
            move_vals['line_ids'] = [
                (0, 0, {
                    'account_id': account_cash.id,
                    'debit': 0.0,
                    'credit': diff,
                    'name': _('Cash surplus'),
                }),
                (0, 0, {
                    'account_id': gain_account.id,
                    'debit': diff,
                    'credit': 0.0,
                    'name': _('Cash surplus'),
                }),
            ]
        else:
            # Hay menos efectivo del esperado → PÉRDIDA
            loss_account = self.cash_id.loss_account_id
            abs_diff = abs(diff)
            move_vals['line_ids'] = [
                (0, 0, {
                    'account_id': account_cash.id,
                    'debit': abs_diff,
                    'credit': 0.0,
                    'name': _('Cash shortage'),
                }),
                (0, 0, {
                    'account_id': loss_account.id,
                    'debit': 0.0,
                    'credit': abs_diff,
                    'name': _('Cash shortage'),
                }),
            ]
        move = move_obj.create(move_vals)
        move.action_post()
        return move

    def action_confirm_closed(self):
        self.ensure_one()
        # validamos estado
        if self.cash_id.state == 'closed':
            raise UserError(_("The cash box is already closed."))
        self.cash_id.current_session_id.closing_note = self.closing_note
        # asientos de diferencia de cierre
        if self.suggested_balance != self.final_balance:
            diff_move = self.applied_diff_closing_balance()
            self.cash_id.current_session_id.diff_move_id = diff_move.id
        # proceso de cierre
        self.cash_id.closed_cash(self.final_balance)
        # si excede el limite de diferencia, notifica a los administardores de caja
        if self.exceeds_limit:
            for user in self.cash_id.responsible_ids:
                self.env['mail.activity'].create({
                    'res_model_id': self.env['ir.model']._get('cash.box').id,
                    'res_id': self.cash_id.id,
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': 'Revisar exceso de efectivo',
                    'note': f'La caja {self.cash_id.name} se cerró con exceso de diferencia. Por favor, revisa.',
                    'user_id': user.id,
                    'date_deadline': fields.Date.today(),
                })
    
    def _get_payment_summary(self, movement_ids=None):
        """ Obtiene un resumen de los pagos realizados por movimiento """
        
        def categorize_payment(payment):
            """ Categoriza el pago según su tipo """
            if payment.journal_id.type == 'credit' or payment.journal_id.default_account_id.account_type == 'liability_credit_card':
                return 'card'
            elif payment.journal_id.type == 'bank':
                return 'transfer'
            else:
                return 'cash'
        
        payment_summary = {}
        import pdb;pdb.set_trace()
        if not movement_ids:
            movement_ids = self.cash_id.current_session_id.movement_ids
        for movement in movement_ids:
            # instanciamos el diccionario de resumen por movimiento
            summary = {'cash': 0.00, 'transfer': 0.00, 'card': 0.00, 'credit': 0.00}
            # si el movimeinto es factura o cotizacion
            if movement.operation_type in ('invoice', 'quote'):
                # obtenemos los pagos asociados a la factura o cotizacion(factura)
                dict_payments = movement.invoice_id.open_payments()
                payments = self.env['account.payment'].browse(
                    dict_payments.get('res_id') or
                    (dict_payments.get('domain') and dict_payments.get('domain')[0][2]) or
                    []
                ) 
                # iteramos los pagos obtenidos
                for payment in payments:
                    key = categorize_payment(payment)
                    summary[key] += payment.amount
            # si el movimiento es una nota de credito
            elif movement.operation_type == 'refund':
                summary['credit'] += movement.credit_note_id.amount_total
            # si el movimiento es un pago
            else:
                # obtenmos el pago
                payment = movement.payment_id
                key = categorize_payment(payment)
                summary[key] += payment.amount
            payment_summary[movement.id] = summary
        return payment_summary
