from openerp import models, fields, api, _
from datetime import datetime, timedelta
import requests
from openerp.osv import expression

class account_invoice(models.Model):
	_inherit = "account.invoice"

	cod_customer = fields.Many2one('res.partner',"COD Customer",required=True)
	cod_move_id = fields.Many2one('account.move',"Journal Entry Customer COD")

	@api.model
	def move_line_get_cod(self, invoice_id):
		inv = self.env['account.invoice'].browse(invoice_id)
		currency = inv.currency_id.with_context(date=inv.date_invoice)
		company_currency = inv.company_id.currency_id

		res = []
		for line in inv.invoice_line:
			mres = self.move_line_get_item(line)
			mres['invl_id'] = line.id
			res.append(mres)
			tax_code_found = False
			taxes = line.invoice_line_tax_id.compute_all(
				(line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)),
				line.quantity, line.product_id, inv.cod_customer)['taxes']
			for tax in taxes:
				if inv.type in ('out_invoice', 'in_invoice'):
					tax_code_id = tax['base_code_id']
					tax_amount = tax['price_unit'] * line.quantity * tax['base_sign']
				else:
					tax_code_id = tax['ref_base_code_id']
					tax_amount = tax['price_unit'] * line.quantity * tax['ref_base_sign']

				if tax_code_found:
					if not tax_code_id:
						continue
					res.append(dict(mres))
					res[-1]['price'] = 0.0
					res[-1]['account_analytic_id'] = False
				elif not tax_code_id:
					continue
				tax_code_found = True

				res[-1]['tax_code_id'] = tax_code_id
				res[-1]['tax_amount'] = currency.compute(tax_amount, company_currency)

		return res

	@api.model
	def line_get_convert_cod(self, line, part, date,company_id):
		# print "=--==================>",line
		return {
			'date_maturity': line.get('date_maturity', False),
			'partner_id': part,
			'name': line['name'][:64],
			'date': date,
			'debit': line['price']>0 and line['price'],
			'credit': line['price']<0 and -line['price'],
			'account_id': line['account_id'],
			'analytic_lines': line.get('analytic_lines', []),
			'amount_currency': line['price']>0 and abs(line.get('amount_currency', False)) or -abs(line.get('amount_currency', False)),
			'currency_id': line.get('currency_id', False),
			'tax_code_id': line.get('tax_code_id', False),
			'tax_amount': line.get('tax_amount', False),
			'ref': line.get('ref', False),
			'quantity': line.get('quantity',1.00),
			'product_id': line.get('product_id', False),
			'product_uom_id': line.get('uos_id', False),
			'analytic_account_id': line.get('account_analytic_id', False),
		}

	@api.multi
	def finalize_invoice_move_lines_cod(self, move_lines):
		""" finalize_invoice_move_lines(move_lines) -> move_lines

			Hook method to be overridden in additional modules to verify and
			possibly alter the move lines to be created by an invoice, for
			special cases.
			:param move_lines: list of dictionaries with the account.move.lines (as for create())
			:return: the (possibly updated) final move_lines to create for this invoice
		"""
		return move_lines

	@api.multi
	def action_move_create_cod(self):
		""" Creates invoice related analytics and financial move lines for COD Customer"""
		account_invoice_tax = self.env['account.invoice.tax']
		account_move = self.env['account.move']

		for inv in self:
			if inv.type in ('in_invoice', 'in_refund'):
				continue
			# print "=============COD move create============="

			if not inv.company_id.cod_accrue_journal_id.sequence_id:
				raise except_orm(_('Error!'), _('Please define sequence on the journal related to this invoice.'))
			if not inv.invoice_line:
				raise except_orm(_('No Invoice Lines!'), _('Please create some invoice lines.'))
			if inv.cod_move_id:
				continue

			ctx = dict(self._context, lang=inv.partner_id.lang)

			company_currency = inv.company_id.currency_id
			if not inv.date_invoice:
				# FORWARD-PORT UP TO SAAS-6
				if inv.currency_id != company_currency and inv.tax_line:
					raise except_orm(
						_('Warning!'),
						_('No invoice date!'
							'\nThe invoice currency is not the same than the company currency.'
							' An invoice date is required to determine the exchange rate to apply. Do not forget to update the taxes!'
						)
					)
				inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
			date_invoice = inv.date_invoice

			# create the analytical lines, one move line per invoice line
			iml = inv._get_analytic_lines()
			# check if taxes are all computed
			compute_taxes = account_invoice_tax.compute(inv.with_context(lang=inv.partner_id.lang))
			inv.check_tax_lines(compute_taxes)

			# I disabled the check_total feature
			if self.env.user.has_group('account.group_supplier_inv_check_total'):
				if inv.type in ('in_invoice', 'in_refund') and abs(inv.check_total - inv.amount_total) >= (inv.currency_id.rounding / 2.0):
					raise except_orm(_('Bad Total!'), _('Please verify the price of the invoice!\nThe encoded total does not match the computed total.'))

			if inv.payment_term:
				total_fixed = total_percent = 0
				for line in inv.payment_term.line_ids:
					if line.value == 'fixed':
						total_fixed += line.value_amount
					if line.value == 'procent':
						total_percent += line.value_amount
				total_fixed = (total_fixed * 100) / (inv.amount_total or 1.0)
				if (total_fixed + total_percent) > 100:
					raise except_orm(_('Error!'), _("Cannot create the invoice.\nThe related payment term is probably misconfigured as it gives a computed amount greater than the total invoiced amount. In order to avoid rounding issues, the latest line of your payment term must be of type 'balance'."))

			# Force recomputation of tax_amount, since the rate potentially changed between creation
			# and validation of the invoice
			inv._recompute_tax_amount()
			# one move line per tax line
			iml += account_invoice_tax.move_line_get(inv.id)

			if inv.type in ('in_invoice', 'in_refund'):
				ref = inv.reference
			else:
				ref = inv.number

			diff_currency = inv.currency_id != company_currency
			# create one move line for the total and possibly adjust the other lines amount
			total, total_currency, iml = inv.with_context(ctx).compute_invoice_totals(company_currency, ref, iml)

			name = inv.supplier_invoice_number or inv.name or '/'
			totlines = []
			if inv.payment_term:
				totlines = inv.with_context(ctx).payment_term.compute(total, date_invoice)[0]
			if totlines:
				res_amount_currency = total_currency
				ctx['date'] = date_invoice
				for i, t in enumerate(totlines):
					if inv.currency_id != company_currency:
						amount_currency = company_currency.with_context(ctx).compute(t[1], inv.currency_id)
					else:
						amount_currency = False

					# last line: add the diff
					res_amount_currency -= amount_currency or 0
					if i + 1 == len(totlines):
						amount_currency += res_amount_currency

					iml.append({
						'type': 'dest',
						'name': name,
						'price': t[1],
						'account_id': inv.company_id.cod_accrue_account_id.id, #perbaiki disini
						'date_maturity': t[0],
						'amount_currency': diff_currency and amount_currency,
						'currency_id': diff_currency and inv.currency_id.id,
						'ref': ref,
					})
			else:
				# print "***********xxxx**************",totlines
				iml.append({
					'type': 'dest',
					'name': name,
					'price': total,
					'account_id': inv.company_id.cod_accrue_account_id.id, #perbaiki disini,
					'date_maturity': inv.date_due,
					'amount_currency': diff_currency and total_currency,
					'currency_id': diff_currency and inv.currency_id.id,
					'ref': ref,
				})
			date = date_invoice

			part = self.env['res.partner']._find_accounting_partner(inv.cod_customer)

			line = [(0, 0, self.line_get_convert_cod(l, part.id, date, inv.company_id)) for l in iml]
			line = inv.group_lines(iml, line)
			journal = inv.company_id.cod_accrue_journal_id.with_context(ctx)
			if journal.centralisation:
				raise except_orm(_('User Error!'),
						_('You cannot create an invoice on a centralized journal. Uncheck the centralized counterpart box in the related journal from the configuration menu.'))

			line = inv.finalize_invoice_move_lines_cod(line)

			move_vals = {
				#'ref': inv.reference or inv.name,
				'line_id': line,
				'journal_id': journal.id,
				'date': inv.date_invoice,
				'narration': inv.comment,
				'company_id': inv.company_id.id,
			}
			ctx['company_id'] = inv.company_id.id
			period = inv.period_id
			if not period:
				period = period.with_context(ctx).find(date_invoice)[:1]
			if period:
				move_vals['period_id'] = period.id
				for i in line:
					i[2]['period_id'] = period.id

			# ctx['invoice'] = inv
			ctx_nolang = ctx.copy()
			ctx_nolang.pop('lang', None)
			move = account_move.with_context(ctx_nolang).create(move_vals)
			# make the invoice point to that move
			vals = {
				'cod_move_id': move.id,
			}
			inv.with_context(ctx).write(vals)
			# Pass invoice in context in method post: used if you want to get the same
			# account move reference when creating the same invoice after a cancelled one:
			move.post()
		self._log_event()
		return True

	@api.multi
	def action_cancel(self):
		res = super(account_invoice,self).action_cancel()
		cod_moves = self.env['account.move']
		for inv in self:
			if inv.cod_move_id:
				cod_moves += inv.cod_move_id
		self.write({'cod_move_id': False})
		if cod_moves:
			#invalidate the move(s)
			cod_moves.button_cancel()
			# delete the move this invoice was pointing to
			# Note that the corresponding move_lines and move_reconciles
			# will be automatically deleted too
			cod_moves.unlink()
		return res

class account_invoice_line(models.Model):
	_inherit="account.invoice.line"

	name = fields.Char(string='No. Resi')
	recipient = fields.Char(string='Name of Recipient')
	price_cod = fields.Float(string='Price COD')
	price_package = fields.Float(string='Price Package')
	nilai_edc = fields.Char(string='Nilai EDC')
	pod_datetime = fields.Datetime(string='POD Datetime')
	sigesit = fields.Many2one('hr.employee',string='Sigesit')
	internal_status = fields.Selection([('open','Open'),
										('antar','Pengantaran'),
										('sigesit','Sigesit'),
										('lost','Lost'),
										('pusat','Pusat'),
										('rta','RTA'),
										('rtg','Returned to Gerai'),
										('rts','Returned to Shipper'),
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
	cr_gesit_line = fields.Many2one("account.bank.statement.line","CR Line Sigesit",ondelete="set null")
	cr_gesit_id = fields.Many2one("account.bank.statement","CR Sigesit",ondelete="set null")
	cr_admin_line = fields.Many2one("account.bank.statement.line","CR Line Admin",ondelete="set null")
	cr_admin_id = fields.Many2one("account.bank.statement","CR Admin",ondelete="set null")
	bs_line = fields.Many2one("account.bank.statement.line","BS Line Pusat",ondelete="set null")
	bs_id = fields.Many2one("account.bank.statement","BS Pusat",ondelete="set null")
	update_block_failed = fields.Boolean("Update Blocked Status to POD",help="True if update to POD is failed")
	update_unblock_failed = fields.Boolean("Update Unblocked to POD",help="True if update to POD is failed")

	
	def get_all_blocked_sigesit(self,cr,uid,context=None):
		if not context:
			context={}
		now = datetime.today().strftime('%Y-%m-%d')
		# inv_line_ids = self.search([('sigesit','!=',False),('internal_status','in',('sigesit','lost')),('pod_datetime','<=',"(now() - interval '1' day)")])
		query = """select id 
			from account_invoice_line 
			where sigesit is not NULL 
			and internal_status in ('sigesit','lost') 
			and pod_datetime <= (now() - interval '1' day)
			and pod_datetime >= (now() - interval '40' day);"""
		cr.execute(query)

		inv_lines = cr.fetchall()
		inv_line_ids=[]
		if inv_lines:
			inv_line_ids = [x[0] for x in inv_lines]
			sigesit = []
			for line in self.pool.get('account.invoice.line').browse(cr,uid,inv_line_ids):
				if line.sigesit.nik:
					sigesit.append(line.sigesit.nik)
		sigesit = list(set(sigesit))
		for s in sigesit:
			url = 'http://pickup.sicepat.com:8087/api/integration/blocksigesit?username='+s
			r = requests.get(url)
			print "===============",r
		return sigesit
		# for invl in inv_line_ids:


class account_journal(models.Model):
	_inherit = "account.journal"

	cod_user_responsible = fields.Many2many('res.users', 'account_journal_res_users_rel', 'journal_id', 'user_id', string='COD Responsibles' )
	cod_admin_user = fields.Many2many('res.users', 'account_journal_admin_res_users_rel', 'journal_id', 'user_id', string='COD Admin Responsibles' )


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
						'invoce_line_id': inv_line.id,
						'account_analytic_id': inv_line.account_analytic_id and inv_line.account_analytic_id.id or False,
						'statement_id'	: cr_id,
					}
					cr_line_id = self.pool.get('account.bank.statement.line').create(cr,uid,cr_lines)
					inv_line.write({'cr_gesit_line':cr_line_id,'cr_gesit_id':cr_id})
		return True

