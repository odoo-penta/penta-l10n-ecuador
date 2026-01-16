# -*- coding: utf-8 -*-
from odoo import models, api

import traceback
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("[DEBUG] Se va a crear el asiento")
        _logger.info("TRACE:\n%s","".join(traceback.format_stack()))
        return super().create(vals_list)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("[DEBUG] Se va a crear linea de asiento")
        _logger.info("[DEBUG] Valores: %s", vals_list)
        _logger.info("TRACE:\n%s","".join(traceback.format_stack()))
        return super().create(vals_list)
