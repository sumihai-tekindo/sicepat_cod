from openerp import models, fields, api, _
from datetime import datetime, timedelta
import requests
from openerp.osv import osv, expression

class account_invoice_line_retur(models.TransientModel):
	_name = "account.invoice.line.retur"

	user_id = fields.Many2one('res.users',"User Responsible")
	line_ids = fields.Many2many("account.invoice.line","account_invoice_line_retur_rel","retur_id","line_id","Invoice Lines")


	def default_get(self, cr, uid, fields, context=None):
		res = super(account_invoice_line_retur,self).default_get(cr,uid,fields,context=context)
		print "============",context
		res.update({
			'user_id':uid,
			'line_ids':context.get('active_ids',False),
			})

		return res

	def return_package(self,cr,uid,ids,context=None):
		if not context:
			context={}
		for o in self.browse(cr,uid,ids,context=context):
			invoice_lines = [x.id for x in o.line_ids]
			print "===============",invoice_lines
			self.pool.get('account.invoice.line').package_returned(cr,uid,invoice_lines,context=context)
		return True