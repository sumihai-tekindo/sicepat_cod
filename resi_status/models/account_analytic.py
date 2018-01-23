from openerp import models, fields
from datetime import datetime

from openerp.osv import expression

class account_analytic_account(models.Model):
	_inherit = "account.analytic.account"

	user_admin_cabang = fields.Many2many('res.users', 'analytic_res_users_rel', 'analytic_id', 'user_id', string='Admin Cabang' )