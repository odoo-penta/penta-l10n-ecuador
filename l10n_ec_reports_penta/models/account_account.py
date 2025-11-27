from odoo import models, fields
import io
import base64
import xlsxwriter


class AccountAccount(models.Model):
    _inherit = 'account.account'

    hide_in_report = fields.Boolean(string="Ocultar en reporte", default=False)

    def _get_group_level(self, group):
        """Nivel real basado en parent_id del grupo."""
        level = 0
        parent = group.parent_id
        while parent:
            level += 1
            parent = parent.parent_id
        return level

    def _get_account_level(self, account):
        """
        Nivel REAL de la cuenta:
        nivel = nivel del grupo + 1
        """
        if account.group_id:
            return self._get_group_level(account.group_id) + 1
        return 0  # cuentas sin grupo

    def _build_group_tree(self, groups):
        """Retorna lista jerárquica de grupos."""
        tree = []
        lookup = {g.id: {'group': g, 'children': []} for g in groups}

        for g in groups:
            if g.parent_id and g.parent_id.id in lookup:
                lookup[g.parent_id.id]['children'].append(lookup[g.id])
            else:
                tree.append(lookup[g.id])

        return tree

    def _walk_tree(self, node, full_list):
        """Recorre el árbol y agrega grupos + cuentas al listado final."""
        group = node['group']
        group_level = self._get_group_level(group)

        full_list.append({
            'level': group_level,
            'type': 'Grupo',
            'code': group.code_prefix_start,
            'name': group.name,
            'reconcile': '',
        })

        # Cuentas del grupo
        accounts_in_group = self.env['account.account'].search([
            ('group_id', '=', group.id),
            ('deprecated', '!=', True),
        ], order='code')

        for account in accounts_in_group:
            full_list.append({
                'level': group_level + 1,
                'type': 'Cuenta',
                'code': self._format_code(account.code),
                'name': account.name,
                'reconcile': account.reconcile,
            })

        # Procesar subgrupos
        for child in node['children']:
            self._walk_tree(child, full_list)
            
    def _format_code(self, code):
        if not code:
            return ''
        return code.replace('.', '')

    #  Exportar excel

    def action_export_account_group_tree_excel(self):

        # 1. Obtener grupos y ordenarlos
        groups = self.env['account.group'].search([], order='code_prefix_start')

        # 2. Construir árbol real basado en parent_id
        group_tree = self._build_group_tree(groups)

        # 3. Lista final en orden jerárquico
        full_list = []

        for root in group_tree:
            self._walk_tree(root, full_list)

        # 4. Cuentas sin grupo
        accounts_without_group = self.env['account.account'].search([
            ('group_id', '=', False),
            ('deprecated', '!=', True),
        ], order='code')

        for account in accounts_without_group:
            full_list.append({
                'level': self._get_account_level(account),
                'type': 'Cuenta',
                'code': self._format_code(account.code),
                'name': account.name,
                'reconcile': account.reconcile,
            })

        # CREAR EXCEL

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Plan de Cuentas")

        header = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#D9D9D9'})
        border = workbook.add_format({'border': 1})
        center = workbook.add_format({'border': 1, 'align': 'center'})

        worksheet.set_column('A:A', 18)
        worksheet.set_column('B:B', 50)
        worksheet.set_column('C:C', 10)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 20)

        headers = ['Código contable', 'Nombre de la cuenta', 'Nivel', 'Tipo', 'Permitir conciliación']

        row = 0
        for col, h in enumerate(headers):
            worksheet.write(row, col, h, header)

        for item in full_list:
            row += 1

            indent = workbook.add_format({'indent': item['level'], 'border': 1})

            worksheet.write(row, 0, item['code'], border)
            worksheet.write(row, 1, item['name'], indent)
            worksheet.write(row, 2, item['level'], center)
            worksheet.write(row, 3, item['type'], center)
            worksheet.write(row, 4, 'Sí' if item.get('reconcile') else 'No', center)

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