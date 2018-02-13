from openerp import models, fields
from datetime import datetime

from openerp.osv import expression

class rds_destination(models.Model):
	_name = "rds.destination"

	name = fields.Char("Name",required=True)
	province = fields.Char("Province")
	city = fields.Char("City")
	subdistrict = fields.Char("Subdistrict")
	code = fields.Char("Kode",required=True)
	user_ids = fields.Many2many('res.users','res_user_rds_destination_rel','rds_dest_id','user_id', string='Maintainer(s)')

	