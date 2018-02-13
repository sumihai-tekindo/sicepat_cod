from openerp import models, fields
from datetime import datetime

class res_users(models.Model):
	_inherit = "res.users"

	destination_ids = fields.Many2many('rds.destination','res_user_rds_destination_rel','user_id','rds_dest_id', string='Maintained Location(s)')

	