# -*- coding: utf-8 -*-
# from odoo import http


# class StockReportAbc(http.Controller):
#     @http.route('/stock_report_abc/stock_report_abc', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/stock_report_abc/stock_report_abc/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('stock_report_abc.listing', {
#             'root': '/stock_report_abc/stock_report_abc',
#             'objects': http.request.env['stock_report_abc.stock_report_abc'].search([]),
#         })

#     @http.route('/stock_report_abc/stock_report_abc/objects/<model("stock_report_abc.stock_report_abc"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('stock_report_abc.object', {
#             'object': obj
#         })

