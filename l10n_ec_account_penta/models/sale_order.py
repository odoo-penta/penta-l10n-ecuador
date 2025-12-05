# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    active_financing = fields.Boolean(string='Active Financing', default=False)
    factor_to_apply = fields.Float(string='Entry amount')
    entry_percentage = fields.Float(string='Entry (%)', default=0)
    risk_percentage = fields.Float(string='Risk (%)', default=0)
    interest = fields.Float(string='Interest (%)', default=0, readonly=True)
    month_interest = fields.Float(string='Monthly Interest (%)', compute='_compute_monthly_interest', readonly=True)
    months_of_grace = fields.Integer(string='Months of Grace', default=0)
    apply_interest_grace = fields.Boolean(string='Apply Interest Grace', default=False, readonly=True)
    proration = fields.Boolean(string='Proration', readonly=True)
    minimum_fee = fields.Monetary(string='Minimum Fee', default=0.0, readonly=True)
    payment_period = fields.Integer(
        comodel_name='account.payment.term',
        related='payment_term_id.installments_number',
        string='Payment Period (Months)',
        readonly=True,
    )
    line_deferred_ids = fields.One2many('sale.order.line.deferred', 'sale_order_id', string='Deferred Lines', readonly=True)
    financing_amount = fields.Monetary(string='Financing Amount', readonly=True)
    recalculation_pending = fields.Boolean(string='Recalculation Pending', default=False)
    financing_locked = fields.Boolean(
        string="Financing Locked",
        compute="_compute_financing_locked",
        store=False
    )
    applied_financing = fields.Boolean(string='Applied Financing', default=False)
    total_interest_amount = fields.Monetary(
        string='Total Interest Amount',
        compute='_compute_total_interest_amount',
        store=False
    )
    
    @api.depends('line_deferred_ids.interest_amount', 'line_deferred_ids.additional_grace_interest')
    def _compute_total_interest_amount(self):
        for order in self:
            total_interest = sum(order.line_deferred_ids.mapped('interest_amount'))
            total_grace_interest = sum(order.line_deferred_ids.mapped('additional_grace_interest'))
            order.total_interest_amount = total_interest + total_grace_interest
    
    @api.depends('invoice_ids.state', 'applied_financing')
    def _compute_financing_locked(self):
        for order in self:
            # Facturas ligadas al pedido (confirmadas o borrador)
            invoices = order.invoice_ids.filtered(lambda inv: inv.state in ['draft', 'posted'])
            order.financing_locked = bool(invoices)
            if order.applied_financing:
                order.financing_locked = True
    
    @api.depends('interest')
    def _compute_monthly_interest(self):
        for order in self:
            order.month_interest = order.interest / 12 if order.interest else 0.0
    
    def _compute_financing_amounts(self, reward=None):
        """Calcula:
            - monto_base_financiable
            - monto_base_contado
            - iva_financiable
            - total_sujeto_financiamiento
        """
        self.ensure_one()
        financing_base_amount = 0.0 
        counted_base_amount = 0.0 
        financing_iva = 0.0
        total_subject_financing = 0.0
        # Obtener productos financiables
        program = False
        if not reward:
            card = self.env['loyalty.card'].search([('order_id', '=', self.id)], limit=1)
            if card:
                program = card.program_id
        else:
            program = reward.program_id
        if program:
            product_ids = program.rule_ids.mapped('valid_product_ids').ids
            for line in self.order_line:
                taxes_res = line.tax_id.compute_all(
                    line.price_unit * (1 - (line.discount / 100)),
                    currency=self.currency_id,
                    quantity=line.product_uom_qty,
                    product=line.product_id,
                    partner=self.partner_id
                )
                base_amount = taxes_res['total_excluded']
                iva_amount = sum(t['amount'] for t in taxes_res['taxes'])
                # Sumar base e impuestos SOLO para las líneas financiables
                if line.product_id.id in product_ids:
                    financing_base_amount += base_amount
                    financing_iva += iva_amount
                else:
                    counted_base_amount += base_amount
            total_subject_financing = financing_base_amount + financing_iva
        return {
            'financing_base_amount': financing_base_amount,
            'counted_base_amount': counted_base_amount,
            'financing_iva': financing_iva,
            'total_subject_financing': total_subject_financing,
        }
    
    def calculate_lines_deferred(self):
        self.ensure_one()
        self.line_deferred_ids.unlink()
        # Verificar el monto a financiar
        financing_amount = self.financing_amount
        if financing_amount <= 0.00:
            return
        entry_percentage = self.entry_percentage / 100
        risk_percentage = self.risk_percentage / 100
        month_interest = self.month_interest / 100
        # Calcular monto de entrada
        calc_entry_amount = self.env.context.get('calc_entry_amount')
        if calc_entry_amount:
            entry_amount = round((financing_amount * entry_percentage), 2)
            self.factor_to_apply = entry_amount
        new_total_amount = round(financing_amount - self.factor_to_apply, 2)
        # Calculo de cuota fija
        fixed_fee = round(new_total_amount*(month_interest*((1+month_interest)**self.payment_period) / (((1+month_interest)**self.payment_period)-1)), 2)
        # Calcular tabla
        balance = new_total_amount
        base_date = fields.Date.to_date(self.date_order)
        interest_amount = round(balance * month_interest, 2)
        total_grace_interest_amount = self.months_of_grace * interest_amount if self.apply_interest_grace else 0.0
        interest_grace_value_line = round(total_grace_interest_amount / self.payment_period, 2)

        for i in range(1, (self.payment_period + self.months_of_grace) + 1):
            # Calcular fecha de vencimiento
            if i == 1:
                line_date = base_date
            else:
                line_date = line_date + relativedelta(days=30)
            # Si es mes de gracia
            if i <= self.months_of_grace:
                interest_line = 0.00
                amortization = 0.00
                grace_interest = 0.00
                line_fixed_fee = 0.00
                # Si aplica interes en meses de gracia y NO es prorrateado
                if self.apply_interest_grace and not self.proration:
                    interest_line = interest_amount
                    line_fixed_fee = interest_amount
            # Si no es mes de gracia
            else:
                interest_line = round(balance * month_interest, 2)
                amortization = round(fixed_fee - interest_line, 2)
                grace_interest = 0.00
                line_fixed_fee = fixed_fee
                if self.apply_interest_grace and self.proration:
                    grace_interest = interest_grace_value_line
                    line_fixed_fee += interest_grace_value_line
            if i == (self.payment_period + self.months_of_grace):
                amortization = round(balance, 2)
                line_fixed_fee = round(interest_line + amortization + grace_interest, 2)
            self.env['sale.order.line.deferred'].create({
                'sale_order_id': self.id,
                'month': i,
                'initial_balance': balance,
                'interest_amount': interest_line,
                'amortization': amortization,
                'additional_grace_interest': grace_interest,
                'fixed_fee': line_fixed_fee,
                'final_balance': round(balance - amortization, 2),
                'due_date': line_date,
            })
            balance -= amortization

    def _apply_program_reward(self, reward, coupon, **kwargs):
        self.ensure_one()
        # Use the old lines before creating new ones. These should already be in a 'reset' state.
        old_reward_lines = kwargs.get('old_lines', self.env['sale.order.line'])
        if reward.is_global_discount:
            global_discount_reward_lines = self._get_applied_global_discount_lines()
            global_discount_reward = global_discount_reward_lines.reward_id
            if (
                global_discount_reward
                and global_discount_reward != reward
                and self._best_global_discount_already_applied(global_discount_reward, reward)
            ):
                return {'error': _("A better global discount is already applied.")}
            elif global_discount_reward and global_discount_reward != reward:
                # Invalidate the old global discount as it may impact the new discount to apply
                global_discount_reward_lines._reset_loyalty(True)
                old_reward_lines |= global_discount_reward_lines
        if not reward.program_id.is_nominative and reward.program_id.applies_on == 'future' and coupon in self.coupon_point_ids.coupon_id:
            return {'error': _('The coupon can only be claimed on future orders.')}
        elif self._get_real_points_for_coupon(coupon) < reward.required_points:
            return {'error': _('The coupon does not have enough points for the selected reward.')}
        # Add campos para financiar
        if reward.program_type == 'financing_promotion':
            self.active_financing = True
            self.entry_percentage = reward.entry_percentage
            self.risk_percentage = reward.risk_percentage
            self.interest = reward.interest
            self.months_of_grace = reward.months_of_grace
            self.apply_interest_grace = reward.apply_interest_grace
            self.minimum_fee = reward.minimum_fee
            self.payment_period = reward.payment_period
            self.payment_term_id = reward.apply_payment_terms.id
            self.financing_amount = self._compute_financing_amounts(reward)['total_subject_financing']
            # Calcular líneas diferidas
            self.with_context(calc_entry_amount=True).calculate_lines_deferred()
        else:
            reward_vals = self._get_reward_line_values(reward, coupon, **kwargs)
            self._write_vals_from_reward_vals(reward_vals, old_reward_lines)
        return {}
    
    @api.onchange(
        'factor_to_apply',
        'entry_percentage',
        'risk_percentage',
        'interest',
        'month_interest',
        'apply_interest_grace',
        'months_of_grace',
        'minimum_fee',
        'payment_period',
    )
    def _onchange_recalculate_deferred(self):
        self.recalculation_pending = True
        
    def action_recalculate_financing(self):
        for order in self:
            order.calculate_lines_deferred()
            order.recalculation_pending = False
            
    def action_apply_financing(self):
        for order in self:
            product = self.env['product.template'].search([('financing_interest_product', '=', True)], limit=1)
            if not product:
                raise ValidationError(_("No 'Financing Interest Product' configured in the system."))
            self.env['sale.order.line'].create({
                'order_id': self.id,
                'product_id': product.product_variant_id.id,
                'product_uom_qty': 1,
                'price_unit': self.total_interest_amount,
                'tax_id': [(6, 0, product.taxes_id.ids)],
            })
            order.applied_financing = True
    
class SaleOrderLineDeferred(models.Model):
    _name = 'sale.order.line.deferred'
    
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='sale_order_id.currency_id',
        store=True,
        readonly=True
    )
    month = fields.Integer(string='Month')
    initial_balance = fields.Monetary(string='Initial Balance', currency_field='currency_id')
    interest_amount = fields.Monetary(string='Interest Amount', currency_field='currency_id')
    amortization = fields.Monetary(string='Amortization', currency_field='currency_id')
    additional_grace_interest = fields.Monetary(string='Additional Grace Interest', currency_field='currency_id')
    final_balance = fields.Monetary(string='Final Balance', currency_field='currency_id')
    fixed_fee = fields.Float(string='Fixed fee', currency_field='currency_id')
    due_date = fields.Date(string='Due Date')
