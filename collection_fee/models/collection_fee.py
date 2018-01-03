from openerp import models, fields, api


class collection_fee(models.Model):
	_inherit="res.partner"

	collection_fee = fields.Float(compute='_compute_collection_fee',string='Collection Fee',readonly=True)
	commision_percentage = fields.Float(string='Commision Percentage')


	@api.one
	@api.depends('commision_percentage')
	def _compute_collection_fee(self):
		# collection_fee_amt=0.0
		# collection_fee_journals = self.env['account.journal'].search([('type','=','sale')])
		# collection_fee_domain = [('partner_id','=',self.id),('account_id.type','=','receivable'),('reconcile_id','=',False),('credit','>',0.0),('journal_id','in',[collection_fee_journals.id for collection_fee_journal in collection_fee_journals])]
		# collection_fee_move_lines = self.env['account.move.line'].search(collection_fee_domain)
		# print('collection_fee_move_lines: %s' % collection_fee_move_lines)

		# if collection_fee_move_lines:
		# 	for move_line in collection_fee_move_lines:
		# 		if move_line.amount_residual>0.0:
		# 			collection_fee_amt+=move_line.amount_residual

		self.collection_fee=self.credit*self.commision_percentage
