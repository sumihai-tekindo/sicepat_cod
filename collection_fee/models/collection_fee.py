from openerp import models, fields


class collection_fee(models.Model):
	_inherit="res.partner"

	collection_fee = fields.Float(string='Collection Fee')
	