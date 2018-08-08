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
		if context.get('active_ids',False):
			invl = self.pool.get('account.invoice.line').browse(cr,uid,context.get('active_ids'))
			emp=False
			for ix in invl:
				if emp!=False and emp!=ix.sigesit.id:
					raise osv.except_osv(_('Error!'),_("Tidak bisa menginput setoran dari resi yang berbeda kurir!"))
				else:	
					emp = ix.sigesit.id
				if ix.internal_status!='DLV':
					raise osv.except_osv(_('Error!'),_("Tidak bisa menginput setoran dari resi yang statusnya belum Delivered !"))

		res.update({
			'user_id':uid,
			'employee_id':emp,
			'reconciliation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			'line_ids':context.get('active_ids',False),
			'journal_id':journal_id[0] or False
			})

		return res

	def create_cash_register_sigesit(self,cr,uid,ids,context=None):
		if not context:context={}
		context.update({'journal_type':'cash','register_type':'cr_gesit'})
		context2={'journal_type':'cash','register_type':'cr_admin'}

		period_pool = self.pool.get('account.period')
		
		for picker in self.browse(cr,uid,ids,context=context):
			date_period = picker.reconciliation_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
			pids = period_pool.find(cr, uid, dt=date_period, context=context)
			user = self.pool.get('res.users').browse(cr,uid,uid)
			journal_admin = self.pool.get("account.journal").search(cr,uid,[('cod_admin_user','=',uid),('type','=','cash')])
			if not journal_admin:
				raise osv.except_osv(_('Error!'),_("There is no journal defined for Admin Cabang Cash Account, please set the user responsible in Journal"))


			if pids:
				context.update({'period_id':pids[0]})
				cash_register = {
					'journal_id'		: picker.journal_id.id or False,
					# 'date_period'		: date_period,
					'period_id'			: pids[0],
					'sigesit'			: picker.employee_id and picker.employee_id.id,
					'partner_sigesit'	: picker.employee_id and picker.employee_id.user_id and picker.employee_id.user_id.partner_id and picker.employee_id.user_id.partner_id.id,
					'analytic_account_id': user.analytic_id and user.analytic_id.id or False,
				}

				context2.update({'period_id':pids[0]})
				cash_register_admin = {
					'journal_id'	: journal_admin[0] or False,
					# 'date_period'	: date_period,
					'period_id'		: pids[0],
					'analytic_account_id': user.analytic_id and user.analytic_id.id or False,
				}
				
			if picker.existing_id:
				cr_id = picker.existing_id and picker.existing_id.id
			else:
				cr_id = self.pool.get('account.bank.statement').create(cr,uid,cash_register,context=context)

			cr_adm_id = self.pool.get('account.bank.statement').create(cr,uid,cash_register_admin,context=context2)
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
			
					# partner_sigesit = cgesit.partner_sigesit and cgesit.partner_sigesit.id
					account_analytic_id = self.pool.get('account.analytic.account').search(cr,uid,[('user_admin_cabang','=',uid),('type','=','normal')])
					linex = [inv_line.id]
					customer =inv_line.partner_id.id
			
					cr_lines_admin = {
						'awb_number'	: inv_line.name,
						'partner_id'	: customer,
						'company_id'	: user.company_id.id,
						'name'			: inv_line.name,
						'date'			: date_period,
						'amount'		: inv_line.price_subtotal,
						'internal_status':'cabang',
						'account_id'	: picker.journal_id and picker.journal_id.default_debit_account_id and picker.journal_id.default_debit_account_id.id,
						'account_analytic_id': inv_line.account_analytic_id and inv_line.account_analytic_id.id or False,
						'invoice_line_ids':[(4,linex)],
						'statement_id'	: cr_adm_id,
						'cr_gesit_id'	: cr_id,
						'cr_gesit_line_id'	: cr_line_id,

					}
					cr_line_id_adm = self.pool.get('account.bank.statement.line').create(cr,uid,cr_lines_admin)
					inv_line.write({'internal_status':'cabang','cr_gesit_line':cr_line_id,'cr_gesit_id':cr_id,'cr_admin_line':cr_line_id,'cr_admin_id':cr_id})

			self.pool.get('account.bank.statement').write(cr,uid,cr_id,{'admin_receipt_id':cr_adm_id},context=context)
			self.pool.get('account.bank.statement').button_open(cr,uid,cr_id,context=context)
			self.pool.get('account.bank.statement').button_confirm_cash(cr,uid,cr_id,context=context)
			self.pool.get('account.bank.statement').button_open(cr,uid,cr_adm_id,context=context2)
			self.pool.get('account.bank.statement').button_confirm_cash(cr,uid,cr_adm_id,context=context2)
		# return True
		print "===================",[cr_id]
		datas = {
			 'ids': [cr_id],
			 'model': 'account.bank.statement',
			 # 'form': []
			}
		# return True
		return {
			'type': 'ir.actions.report.xml',
			'report_name': 'resi_status.tanda_terima',
			'datas': datas,
			}

