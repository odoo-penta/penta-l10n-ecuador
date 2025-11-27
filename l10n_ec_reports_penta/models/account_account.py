from odoo import models, fields
import io
import base64
import xlsxwriter


class AccountAccount(models.Model):
    _inherit = 'account.account'

    hide_in_report = fields.Boolean(string="Ocultar en reporte", default=False)

    def _format_code(self, code):
        if not code:
            return ''

        code = code.replace('.', '')

        if len(code) == 1:
            first = code
            rest = ''

        elif len(code) == 2:
            first = code[0] + "0" + code[1]
            rest = ''

        elif len(code) == 3:
            first = code[0] + "0" + code[2]
            rest = ''

        else:
            first = code[0] + "0" + code[2]
            rest = code[3:]

        if rest:
            parts = [rest[i:i+2] for i in range(0, len(rest), 2)]
            return first + "." + ".".join(parts)

        return first

    def _get_level_from_code(self, formatted_code):
        return formatted_code.count('.') + 1 if formatted_code else 1

    def _get_account_type_label(self, acc):
        selection = acc._fields['account_type'].selection
        value = acc.account_type
        for key, label in selection:
            if key == value:
                return label
        return ''

    def _hierarchy_key(self, code):
        if not code:
            return [999999]
        return [int(x) for x in code.split('.')]

    # EXPORTAR EXCEL COMPLETO
    def action_export_account_group_tree_excel(self):

        full_list = []

        groups = self.env['account.group'].search([])

        for g in groups:
            formatted = self._format_code(g.code_prefix_start)

            full_list.append({
                'level': self._get_level_from_code(formatted),
                'type': '',
                'code': formatted,
                'name': g.name,
                'reconcile': '',
                'is_group': True,
            })

        accounts = self.env['account.account'].search([
            ('deprecated', '!=', True)
        ])

        for acc in accounts:
            formatted = self._format_code(acc.code)

            full_list.append({
                'level': self._get_level_from_code(formatted),
                'type': self._get_account_type_label(acc),
                'code': formatted,
                'name': acc.name,
                'reconcile': acc.reconcile,
                'is_group': False,
            })

        full_list = sorted(full_list, key=lambda x: self._hierarchy_key(x['code']))

        # CREAR EXCEL
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Plan de Cuentas")

        header = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#D9D9D9'})
        border = workbook.add_format({'border': 1})
        center = workbook.add_format({'border': 1, 'align': 'center'})
        bold = workbook.add_format({'bold': True, 'border': 1})

        worksheet.set_column('A:A', 18)
        worksheet.set_column('B:B', 50)
        worksheet.set_column('C:C', 10)
        worksheet.set_column('D:D', 25)
        worksheet.set_column('E:E', 20)

        headers = ['Código contable', 'Nombre de la cuenta', 'Nivel', 'Tipo', 'Permitir conciliación']

        row = 0
        for col, h in enumerate(headers):
            worksheet.write(row, col, h, header)

        for item in full_list:
            row += 1

            indent = workbook.add_format({'indent': item['level'] - 1, 'border': 1})

            if item['is_group']:
                worksheet.write_string(row, 0, item['code'], bold)
                worksheet.write(row, 1, item['name'], bold)
                worksheet.write(row, 2, item['level'], center)
                worksheet.write(row, 3, '', center)
                worksheet.write(row, 4, '', center)
            else:
                worksheet.write_string(row, 0, item['code'], border)
                worksheet.write(row, 1, item['name'], indent)
                worksheet.write(row, 2, item['level'], center)
                worksheet.write(row, 3, item['type'], center)
                worksheet.write(row, 4, 'Sí' if item['reconcile'] else 'No', center)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())

        attachment = self.env['ir.attachment'].create({
            'name': 'plan_de_cuentas.xlsx',
            'type': 'binary',
            'datas': file_data,
            'res_model': 'res.users',
            'res_id': self.env.user.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }


class AccountGroup(models.Model):
    _inherit = 'account.group'

    account_move = fields.Boolean(string="Cuenta de movimiento", default=False)