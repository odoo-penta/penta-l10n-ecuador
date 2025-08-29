from odoo import models, fields

class ExportInventoryMonthWizard(models.TransientModel):
    _name = 'export.inventory.month.wizard'
    _description = 'Exportar Inventario por Mes'

    MONTHS = [
        ('1', 'Enero'),
        ('2', 'Febrero'),
        ('3', 'Marzo'),
        ('4', 'Abril'),
        ('5', 'Mayo'),
        ('6', 'Junio'),
        ('7', 'Julio'),
        ('8', 'Agosto'),
        ('9', 'Septiembre'),
        ('10', 'Octubre'),
        ('11', 'Noviembre'),
        ('12', 'Diciembre'),
    ]

    
    month = fields.Selection(
        selection=MONTHS,
        string="Mes",
        required=True
    )
    year = fields.Selection(
        [(str(y), str(y)) for y in range(2022, fields.Date.today().year + 1)],
        string="Año", required=True
    )

    def export_xlsx(self):
        print('Exportando inventario para el mes:', self.month, 'año:', self.year)
        return {
            'type': 'ir.actions.act_url',
            'url': f'/inventory_export_xlsx?month={self.month}&year={self.year}',
            'target': 'self',
        }
