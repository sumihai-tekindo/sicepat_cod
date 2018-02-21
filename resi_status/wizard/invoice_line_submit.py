from openerp import models, fields, api, _
from datetime import datetime, timedelta
import requests
from openerp.osv import osv, expression

class account_invoice_line_submit(models.TransientModel):
	_name = "account.invoice.line.submit"

	partner_id = fields.Many2one('res.partner','Partner')
	user_id = fields.Many2one('res.users',"User Responsible")
	date_invoice = fields.Date("Invoice Date")
	line_ids = fields.Many2many("account.invoice.line","account_invoice_line_submit_rel","submit_id","line_id","Invoice Lines")
	journal_id = fields.Many2one('account.journal',"Supplier Invoice Journal")
	existing_id = fields.Many2one('account.invoice','Existing Supplier Invoice',domain="[('invoice_type','=','in_invoice'),('state','=','draft')]")

	def default_get(self, cr, uid, fields, context=None):
		res = super(account_invoice_line_submit,self).default_get(cr,uid,fields,context=context)
		journal_id = self.pool.get("account.journal").search(cr,uid,[('type','=','purchase')])
		if not journal_id:
			raise osv.except_osv(_('Error!'),_("There is no journal defined for Supplier Invoice"))
		invoice_line_ids = context.get('active_ids',False)
		partners = []
		for x in self.pool.get('account.invoice.line').browse(cr,uid,invoice_line_ids):
			partners.append(x.invoice_id.cod_customer.id)
		partners = list(set(partners))
		if len(partners)>1:
			raise osv.except_osv(_('Error!'),_("You cannot submit AWBs that belongs to different partner in one invoice"))
		res.update({
			'user_id':uid,
			'date_invoice': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			'line_ids':context.get('active_ids',False),
			'journal_id':journal_id[0] or False,
			'partner_id': partners and partners[0] or False
			})

		return res

	def create_supplier_invoice(self,cr,uid,ids,context=None):
		if not context:context={}
		context.update({'default_type': 'in_invoice', 'type': 'in_invoice', 'journal_type': 'purchase'})
		period_pool = self.pool.get('account.period')
		for picker in self.browse(cr,uid,ids,context=context):
			date_invoice = picker.date_invoice or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
			pids = period_pool.find(cr, uid, dt=date_invoice, context=context)
			user = self.pool.get('res.users').browse(cr,uid,uid)
			
			invoice ={
				'partner_id'	:	picker.partner_id.id,
				'date_invoice'	:	date_invoice,
				'journal_id'	:	picker.journal_id.id,
				'invoice_type'	:	'in_invoice',
				'account_id'	:	picker.partner_id.property_account_payable.id,
				'state'			:	'draft',
				'sales_person'	:	uid,
				'invoice_line'	:	[],
				}
			if picker.existing_id:
				inv_id = picker.existing_id and picker.existing_id.id
			else:
				inv_id = self.pool.get('account.invoice').create(cr,uid,invoice,context=context)

			for l in picker.line_ids:
				lines ={
					'name'				:	l.name,
					'account_id'		:	user.company_id.cod_accrue_account_id.id,
					'price_unit'		:	l.price_unit,
					'recipient'			:	l.recipient,
					'price_package'		:	l.price_unit,
					'invoice_id'		: 	inv_id,
					'source_recon_id'	: 	l.id
					}
				lid = self.pool.get('account.invoice.line').create(cr,uid,lines,context=context)				
				l.write({'recon_inv_line_id':lid,'recon_inv_id':inv_id,'internal_status':'submit','external_status':'submitted'})
		return True


