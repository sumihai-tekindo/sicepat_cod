from openerp import models, fields, api, _
from datetime import datetime, timedelta
import requests
from openerp.osv import osv, expression

class account_invoice_line_picker(models.TransientModel):
	_name = "account.invoice.line.picker"


	user_id = fields.Many2one("res.users","Admin Responsible")
	employee_id = fields.Many2one("hr.employee","Sigesit")
	reconciliation_date = fields.Datetime("Tanggal Rekonsiliasi",required=True)
	existing_id = fields.Many2one("account.bank.statement","Existing Reconciliation")
	line_ids = fields.Many2many("account.invoice.line","account_invoice_line_picker_rel","picker_id","line_id","Invoice Lines")
	journal_id = fields.Many2one("account.journal","Journal Kas Sigesit",required=True)

	def default_get(self, cr, uid, fields, context=None):
		res = super(account_invoice_line_picker,self).default_get(cr,uid,fields,context=context)
		journal_id = self.pool.get("account.journal").search(cr,uid,[('cod_user_responsible','=',uid),('type','=','cash')])
		if not journal_id:
			raise osv.except_osv(_('Error!'),_("There is no journal defined for Sigesit Cash Account, please set the user responsible in Journal"))
		res.update({
			'user_id':uid,
			'reconciliation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			'line_ids':context.get('active_ids',False),
			'journal_id':journal_id[0] or False
			})

		return res

	def create_cash_register_sigesit(self,cr,uid,ids,context=None):
		if not context:context={}
		context.update({'journal_type':'cash','register_type':'cr_gesit'})
		period_pool = self.pool.get('account.period')
		for picker in self.browse(cr,uid,ids,context=context):

			date_period = picker.reconciliation_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
			pids = period_pool.find(cr, uid, dt=date_period, context=context)
			user = self.pool.get('res.users').browse(cr,uid,uid)
			if pids:
				context.update({'period_id':pids[0]})
				cash_register = {
					'journal_id'		: picker.journal_id.id or False,
					'date_period'		: date_period,
					'period_id'			: pids[0],
					'sigesit'			: picker.employee_id and picker.employee_id.id,
					'partner_sigesit'	: picker.employee_id and picker.employee_id.user_id and picker.employee_id.user_id.partner_id and picker.employee_id.user_id.partner_id.id,
				}
			if picker.existing_id:
				cr_id = picker.existing_id and picker.existing_id.id
			else:
				cr_id = self.pool.get('account.bank.statement').create(cr,uid,cash_register,context=context)
			line_ids=[]
			if picker.line_ids:
				for inv_line in picker.line_ids:
					cr_lines = {
						'awb_number'	: inv_line.name,
						'partner_id'	: inv_line.invoice_id.partner_id.id,
						'company_id'	: user.company_id.id,
						'recipient'		: inv_line.recipient,
						'name'			: inv_line.name,
						'date'			: date_period,
						'sigesit'		: picker.employee_id and picker.employee_id.id,
						'nilai_edc'		: inv_line.price_cod,
						'price_package'	: inv_line.price_package,
						'price_cod'		: inv_line.price_cod,
						'amount'		: inv_line.price_subtotal,
						'internal_status': 'sigesit',
						'account_id'	: inv_line.invoice_id and inv_line.invoice_id.account_id and inv_line.invoice_id.account_id.id or False,
						'invoice_line_id': inv_line.id,
						'account_analytic_id': inv_line.account_analytic_id and inv_line.account_analytic_id.id or False,
						'statement_id'	: cr_id,
					}
					cr_line_id = self.pool.get('account.bank.statement.line').create(cr,uid,cr_lines)
					inv_line.write({'cr_gesit_line':cr_line_id,'cr_gesit_id':cr_id})
		return True

