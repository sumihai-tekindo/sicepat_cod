from openerp import models, fields,api, _
from datetime import datetime
from openerp.osv import osv, expression

class account_bank_statement_line(models.Model):
	_inherit="account.bank.statement.line"

	awb_number = fields.Char(string='No. Resi')
	recipient = fields.Char(string='Name of Recipient')
	account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
	invoice_line_id = fields.Many2one('account.invoice.line', string='Invoice Line')
	invoice_line_ids = fields.Many2many('account.invoice.line','invoice_line_bs_line_rel','bs_line_id','inv_line_id', string='Invoice Lines')
	price_cod = fields.Float(string='Price COD')
	price_package = fields.Float(string='Price Package')
	nilai_edc = fields.Char(string='Nilai EDC')
	sigesit = fields.Many2one('hr.employee',string='Sigesit')
	internal_status = fields.Selection([('open','Open'),
										('sigesit','Sigesit'),
										('lost','Lost'),
										('pusat','Pusat'),
										('cabang','Cabang'),
										('paid','Paid')],string='Internal Status')
	external_status = fields.Selection([('reconciled','Reconciled'),
										('accepted','Accepted'),
										('payment','Payment')],string='External Status')
	status_retur = fields.Selection([('new','New'),
									('propose','Propose'),
									('rejected','Rejected'),
									('approved','Approved'),
									('closed','Closed')],string='Status Retur')
	cr_gesit_id = fields.Many2one('account.bank.statement','CR Sigesit',ondelete='set null')
	cr_gesit_line_id = fields.Many2one('account.bank.statement.line','CR Sigesit Line',ondelete='set null')

class account_bank_statement_picker(models.TransientModel):
	_name = "account.bank.statement.picker"

	user_id = fields.Many2one("res.users","Admin Responsible")
	reconciliation_date = fields.Datetime("Tanggal Rekonsiliasi",required=True)
	existing_id = fields.Many2one("account.bank.statement","Existing Reconciliation")
	line_ids = fields.Many2many("account.bank.statement","account_bank_statement_picker_rel","picker_id","bs_id","Cash Registers")
	journal_id = fields.Many2one("account.journal","Journal Kas Admin",required=True)
	reference_number = fields.Char("Nomor Transfer")
	notes = fields.Text("Notes")

	def default_get(self, cr, uid, fields, context=None):
		res = super(account_bank_statement_picker,self).default_get(cr,uid,fields,context=context)
		journal_id=False
		if context and context.get('destination','cabang')=='cabang':
			journal_id = self.pool.get("account.journal").search(cr,uid,[('cod_admin_user','=',uid),('type','=','cash')])
			if not journal_id:
				raise osv.except_osv(_('Error!'),_("There is no journal defined for Admin Cabang Cash Account, please set the user responsible in Journal"))

		res.update({
			'user_id':uid,
			'reconciliation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			'line_ids':context.get('active_ids',False),
			'journal_id':journal_id and journal_id[0] or False
			})

		return res


	def create_cash_register_admin(self,cr,uid,ids,context=None):
		if not context:context={}
		context.update({'journal_type':'cash','register_type':'cr_admin'})
		period_pool = self.pool.get('account.period')
		for picker in self.browse(cr,uid,ids,context=context):
			# print "===================",picker.journal_id.id or False
			date_period = picker.reconciliation_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
			pids = period_pool.find(cr, uid, dt=date_period, context=context)
			user = self.pool.get('res.users').browse(cr,uid,uid)
			if pids:
				context.update({'period_id':pids[0]})
				cash_register = {
					'journal_id'	: picker.journal_id.id or False,
					'date_period'	: date_period,
					'period_id'		: pids[0],
				}
			if picker.existing_id:
				cr_id = picker.existing_id and picker.existing_id.id
			else:
				cr_id = self.pool.get('account.bank.statement').create(cr,uid,cash_register,context=context)
			line_ids=[]
			if picker.line_ids:
				for cgesit in picker.line_ids:
					# partner_sigesit = cgesit.partner_sigesit and cgesit.partner_sigesit.id
					account_analytic_id = self.pool.get('account.analytic.account').search(cr,uid,[('user_admin_cabang','=',uid),('type','=','normal')])
					linex = []
					customer = False
					for x in cgesit.line_ids:
						if x.invoice_line_id:
							linex.append(x.invoice_line_id.id)
							customer =x.partner_id.id
					# print "cgesit account------------",cgesit.journal_id
					cr_lines = {
						'partner_id'	: customer,
						'company_id'	: user.company_id.id,
						'name'			: cgesit.name,
						'date'			: date_period,
						'amount'		: cgesit.total_entry_encoding,
						'internal_status': 'cabang',
						'account_id'	: cgesit.journal_id and cgesit.journal_id.default_debit_account_id and cgesit.journal_id.default_debit_account_id.id,
						'account_analytic_id': account_analytic_id and account_analytic_id[0] or False,
						'invoice_line_ids':[(4,linex)],
						'statement_id'	: cr_id,
						'cr_gesit_id'	: cgesit.id,
					}
					cr_line_id = self.pool.get('account.bank.statement.line').create(cr,uid,cr_lines)
					cgesit.write({'admin_receipt_line_id':cr_line_id,'admin_receipt_id':cr_id})
		return True


	def create_bank_statement_finance(self,cr,uid,ids,context=None):
		if not context:context={}
		if context and context.get('destination','cabang')=='cabang':
			raise osv.except_osv(_('Error!'),_("You can not transfer using this option, please use cash receipt option! This can only be done from Cash Register Admin Menu!"))
		else:
			context.update({'journal_type':'bank','register_type':'bs_fin'})
			period_pool = self.pool.get('account.period')
			for picker in self.browse(cr,uid,ids,context=context):
				# print "===================",picker.journal_id.id or False
				date_period = picker.reconciliation_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
				pids = period_pool.find(cr, uid, dt=date_period, context=context)
				user = self.pool.get('res.users').browse(cr,uid,uid)
				if pids:
					context.update({'period_id':pids[0]})
					cash_register = {
						'journal_id'	: picker.journal_id.id or False,
						'date_period'	: date_period,
						'period_id'		: pids[0],
						'notes'			: picker.notes,
						'reference_number':picker.reference_number,
					}
				if picker.existing_id:
					cr_id = picker.existing_id and picker.existing_id.id
				else:
					cr_id = self.pool.get('account.bank.statement').create(cr,uid,cash_register,context=context)
				line_ids=[]
				if picker.line_ids:
					for cgesit in picker.line_ids:
						# partner_sigesit = cgesit.partner_sigesit and cgesit.partner_sigesit.id
						account_analytic_id = self.pool.get('account.analytic.account').search(cr,uid,[('user_admin_cabang','=',uid),('type','=','normal')])
						linex = []
						for x in cgesit.line_ids:
							for y in x.invoice_line_ids:
								linex.append(y.id)

						cr_lines = {
							'partner_id'	: cgesit.user_id.partner_id.id,
							'company_id'	: user.company_id.id,
							'name'			: cgesit.name,
							'date'			: date_period,
							'amount'		: cgesit.total_entry_encoding,
							'internal_status': context.get('destination','pusat'),
							'account_id'	: picker.journal_id and picker.journal_id.default_debit_account_id and picker.journal_id.default_debit_account_id.id,
							'account_analytic_id': account_analytic_id and account_analytic_id[0] or False,
							'invoice_line_ids':[(4,linex)],
							'statement_id'	: cr_id,
							'cr_gesit_id'	: cgesit.id,
						}
						cr_line_id = self.pool.get('account.bank.statement.line').create(cr,uid,cr_lines)
						cgesit.write({'admin_receipt_line_id':cr_line_id,'admin_receipt_id':cr_id})
		return True