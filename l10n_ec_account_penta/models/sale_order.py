# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    interest = fields.Integer(string='Interest (%)', default=0, readonly=True)
    months_of_grace = fields.Integer(string='Months of Grace', default=0)
    apply_interest_grace = fields.Boolean(string='Apply Interest Grace', default=False, readonly=True)
    minimum_fee = fields.Monetary(string='Minimum Fee', default=0.0, readonly=True)

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
            self.interest = reward.interest
            self.months_of_grace = reward.months_of_grace
            self.apply_interest_grace = reward.apply_interest_grace
            self.minimum_fee = reward.minimum_fee
            self.payment_term_id = reward.apply_payment_terms.id
        else:
            reward_vals = self._get_reward_line_values(reward, coupon, **kwargs)
            self._write_vals_from_reward_vals(reward_vals, old_reward_lines)
        return {}