# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    factor_to_apply = fields.Float(string='Entry amount')
    entry_percentage = fields.Float(string='Entry (%)', default=0)
    risk_percentage = fields.Float(string='Risk (%)', default=0)
    interest = fields.Float(string='Interest (%)', default=0, readonly=True)
    months_of_grace = fields.Integer(string='Months of Grace', default=0)
    apply_interest_grace = fields.Boolean(string='Apply Interest Grace', default=False, readonly=True)
    minimum_fee = fields.Monetary(string='Minimum Fee', default=0.0, readonly=True)
    payment_period = fields.Integer(string='Payment Period (Months)', default=0, readonly=True)
    line_deferred_ids = fields.One2many('sale.order.line.deferred', 'sale_order_id', string='Deferred Lines', readonly=True)
    
    def _compute_financing_amounts(self, reward, coupon, **kwargs):
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
        # Obtener productos financiables
        product_ids = reward.program_id.rule_ids.mapped('valid_product_ids').ids
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
    
    def calculate_lines_deferred(self, reward, coupon, **kwargs):
        self.ensure_one()
        self.line_deferred_ids.unlink()
        # Calcular valores iniciales
        financing_amounts = self._compute_financing_amounts(reward, coupon, **kwargs)
        entry_percentage = self.entry_percentage / 100
        risk_percentage = self.risk_percentage / 100
        # Calcular monto de entrada
        entry_amount = round((financing_amounts['total_subject_financing'] * entry_percentage), 2)
        self.factor_to_apply = entry_amount
        new_base_amount = round(financing_amounts['total_subject_financing'], 2)
        new_iva_amount = round(financing_amounts['financing_iva'], 2)
        new_total_sale = round(financing_amounts['total_subject_financing'], 2)
        new_total_amount = round(financing_amounts['total_subject_financing'] - self.factor_to_apply, 2)
        import pdb;pdb.set_trace()

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
            self.entry_percentage = reward.entry_percentage
            self.risk_percentage = reward.risk_percentage
            self.interest = reward.interest
            self.months_of_grace = reward.months_of_grace
            self.apply_interest_grace = reward.apply_interest_grace
            self.minimum_fee = reward.minimum_fee
            self.payment_period = reward.payment_period
            self.payment_term_id = reward.apply_payment_terms.id
            import pdb;pdb.set_trace()
            self.calculate_lines_deferred(reward, coupon, **kwargs)
        else:
            reward_vals = self._get_reward_line_values(reward, coupon, **kwargs)
            self._write_vals_from_reward_vals(reward_vals, old_reward_lines)
        return {}
    
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
    final_balance = fields.Monetary(string='Final Balance', currency_field='currency_id')
    installment = fields.Integer(string='Installment')
    due_date = fields.Date(string='Due Date')
