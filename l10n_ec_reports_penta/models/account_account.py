from odoo import models, fields
import io
import base64
import xlsxwriter

class AccountAccount(models.Model):
    _inherit = 'account.account'

    hide_in_report = fields.Boolean(string="Ocultar en reporte",default= False)
    
    def action_export_account_group_tree_excel(self):
        # Obtener grupos y cuentas
        groups = self.env['account.group'].search([], order='code_prefix_start')
        accounts = self.env['account.account'].search([('deprecated', '!=', True)], order='code')

        # Construir un diccionario con todos los nodos (grupos y cuentas)
        tree_nodes = {}

        # Insertar grupos
        for group in groups:
            tree_nodes[group.code_prefix_start] = {
                'type': 'group',
                'code': group.code_prefix_start,
                'end_code': group.code_prefix_end,
                'name': group.name,
                'children': []
            }

        # Insertar cuentas dentro del grupo correcto
        for account in accounts:
            parent_group = None
            for group in groups:
                if group.code_prefix_start <= account.code <= group.code_prefix_end:
                    parent_group = group.code_prefix_start
                    break

            if parent_group and parent_group in tree_nodes:
                tree_nodes[parent_group]['children'].append({
                    'type': 'account',
                    'code': account.code,
                    'name': account.name,
                })
            else:
                # Si no tiene grupo, lo ponemos como nodo independiente
                tree_nodes[account.code] = {
                    'type': 'account',
                    'code': account.code,
                    'name': account.name,
                }

        # Crear una lista ordenada por code
        full_list = []
        for key in sorted(tree_nodes.keys()):
            node = tree_nodes[key]
            if node['type'] == 'group':
                full_list.append({
                    'level': 0,
                    'code': node['code'],
                    'name': node['name'],
                })
                # Añadir sus cuentas ordenadas
                for child in sorted(node['children'], key=lambda x: x['code']):
                    full_list.append({
                        'level': 1,
                        'code': child['code'],
                        'name': child['name'],
                    })
            else:
                # Cuenta sin grupo
                full_list.append({
                    'level': 0,
                    'code': node['code'],
                    'name': node['name'],
                })

        # Crear archivo Excel
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Plan de Cuentas")

        bold = workbook.add_format({'bold': True})
        worksheet.write('A1', 'Código', bold)
        worksheet.write('B1', 'Nombre', bold)

        row = 1
        for item in full_list:
            worksheet.write(row, 0, self.format_indented_text(item['code']))
            worksheet.write(row, 1, self.format_indented_name(item['code'], item['name']))
            row += 1

       
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
    
    def format_indented_text(self,code):
        level = len(code.split('.')) - 1
        return f"{' ' * (level * 4)}{code}"

    def format_indented_name(self,code, name):
        level = len(code.split('.')) - 1
        return f"{' ' * (level * 4)}{name}"

class AccountGroup(models.Model):
    _inherit = 'account.group'

    account_move = fields.Boolean(string="Cuenta de movimiento",default= False)