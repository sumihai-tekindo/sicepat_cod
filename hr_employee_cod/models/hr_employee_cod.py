from openerp import fields, models, api

class EmployeeCod(models.Model):
    _inherit = 'hr.employee'
    
    cod_position = fields.Selection([('koordinator_cod','Koordinator COD'),
    									('admin_cod','Admin COD'),
    									('sigesit','Sigesit')],string='COD Position')