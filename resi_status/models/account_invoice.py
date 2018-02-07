from openerp import models, fields, api, _
from datetime import datetime, timedelta
import requests
from openerp.osv import osv, expression
import mysql.connector

class account_invoice(models.Model):
	_inherit = "account.invoice"

	cod_customer = fields.Many2one('res.partner',"COD Customer",required=False)
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


	def scheduled_stt_pull(self,cr,uid,context=None):
		
		config = {
			'user': 'rudydarw_damar',
			'password': 'Rudybosnyasicepat168168',
			'host': 'sicepatrds.cchjcxaiivov.ap-southeast-1.rds.amazonaws.com',
			'database': 'rudydarw_sicepat',
			'raise_on_warnings': True,
		}
		cnx = mysql.connector.connect(**config)
		cur = cnx.cursor()
		querystt = """select tgltransaksi,pengirim,nostt,penerima,codNilai 
					from rudydarw_sicepat.stt 
					where codNilai>0.0 and iscodpulled != 1 
					order by tgltransaksi asc,pengirim asc,nostt asc
				 """
		
		cur.execute(querystt)
		result = cur.fetchall()
		

		############################################################################################
		# group the data to make it easier creating invoice
		# {tgl_transaksi:{pengirim:{'00000123123':{'penerima':'nama penerima','price_unit':50000}}}}
		############################################################################################
		data = {}
		all_cod_cust = []
		for r in result:
			
			data_tgl = data.get(r[0],{})
			tgl_pengirim = data_tgl.get(r[1],{})
			all_cod_cust.append(r[1])
			tgl_pengirim.update({r[2]:{'penerima':r[3],'price_unit':r[4]}})
			data_tgl.update({r[1]:tgl_pengirim})
			data.update({r[0]:data_tgl})
		all_cod_cust=list(set(all_cod_cust))

		partner_cod_ids = self.pool.get('res.partner').search(cr,uid,[('name','in',all_cod_cust)])
				# print "----------",nomo
		partner_cod = {}
		if all_cod_cust and partner_cod_ids and (len(all_cod_cust)!=len(partner_cod_ids)):
			for pc in self.pool.get('res.partner').browse(cr,uid,partner_cod_ids):
				partner_cod.update({pc.name:pc.id})
		not_in_partner = []
		for x in all_cod_cust:
			if not partner_cod.get(x,False):
				not_in_partner.append(x)

		for nip in not_in_partner:
			print "-----------------",nip
			if nip and nip!=None and nip !="":
				pt_id = self.pool.get('res.partner').create(cr,uid,{'name':nip,'customer':True,'supplier':True})
				partner_cod.update({nip:pt_id})

		user = self.pool.get('res.users').browse(cr,uid,uid,context=context)
		partner = user.company_id.cod_customer
		domain = [('type', '=', 'sale'),
			('company_id', '=', user.company_id.id)]
		journal_id = self.pool.get('account.journal').search(cr,uid,domain, limit=1)
		created_invoices = []
		for tgl in data:
			if tgl:
				sender = data.get(tgl,{})
				for pengirim in sender:
					if pengirim:
						values = {
							'partner_id'	:	partner.id,
							'date_invoice'	:	tgl.strftime('%Y-%m-%d'),
							'journal_id'	:	journal_id and journal_id[0],
							'invoice_type'	:	'out_invoice',
							'account_id'	:	partner.property_account_receivable.id,
							'state'			:	'draft',
							'sales_person'	:	uid,
							'invoice_line'	:	[],
							'cod_customer'	: 	partner_cod.get(pengirim,False),
						}
						invoice_line = []
						awbs = sender.get(pengirim,{})
						for awb in awbs:
							lines = {
								'name'				:	awb,
								'account_id'		:	user.company_id.account_temp_1.id,
								'price_unit'		:	awbs.get(awb).get('price_unit',0.0),
								'recipient'			:	awbs.get(awb).get('recipient',0.0),
								'price_package'		:	awbs.get(awb).get('price_unit',0.0),
								'internal_status'	:	'open',
							}
							invoice_line.append((0,0,lines))
					values.update({'invoice_line':invoice_line})
					# print "============",values
					inv_id = self.pool.get('account.invoice').create(cr,uid,values)
					if inv_id:
						created_invoices.append(inv_id)
		invoice_line = self.pool.get('account.invoice.line').search(cr,uid,[('invoice_id','in',created_invoices)])
		
		cnx.close()
		cur.close()
		to_update = ""
		for x in self.pool.get('account.invoice.line').browse(cr,uid,invoice_line):
			to_update+="'"+x.name+"',"
		if to_update!="":
			to_update=to_update[:-1]
			query_update = """update stt set iscodpulled=1 where nostt in (%s)"""%to_update
			cnx2 = mysql.connector.connect(**config)
			cur2 = cnx2.cursor()
			cur2.execute(query_update)
			cur2.close()
			cnx2.close()
		return result

class account_invoice_line_payment_type(models.Model):
	_name = "acc.invoice.line.pt"

	name = fields.Char(string='Payment Type Name')
	code = fields.Char(string='Payment Type Code')

	
class account_invoice_line(models.Model):
	_inherit="account.invoice.line"

	name = fields.Char(string='No. Resi')
	recipient = fields.Char(string='Name of Recipient')
	price_cod = fields.Float(string='Price COD')
	price_package = fields.Float(string='Price Package')
	nilai_edc = fields.Char(string='Nilai EDC')
	pod_datetime = fields.Datetime(string='POD Datetime')
	sigesit = fields.Many2one('hr.employee',string='Sigesit')
	payment_type = fields.Many2one('acc.invoice.line.pt',string='Payment Type')
	internal_status = fields.Selection([('open','Open'),
										('antar','Pengantaran'),
										('sigesit','Sigesit'),
										('lost','Lost'),
										('pusat','Pusat'),
										('rta','RTA'),
										('rtg','Returned to Gerai'),
										('rts','Returned to Shipper'),
										('submit','Submitted to Partner'),
										('cabang','Cabang'),
										('paid','Paid')],string='Internal Status')
	external_status = fields.Selection([('submitted','Sumbitted'),
										('reconciled','Reconciled'),
										('accepted','Accepted')],string='External Status')
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
	recon_inv_line_id = fields.Many2one('account.invoice.line','Reconciliation Invoice Line',ondelete="set null")
	recon_inv_id = fields.Many2one('account.invoice','Reconciliation Invoice Line',ondelete="set null")
	source_recon_id = fields.Many2one('account.invoice.line',"Reconciliation AWB Source",)

	def unlink(self,cr,uid,ids,context=None):
		if not context:context={}
		res = super(account_invoice_line,self).unlink(cr,uid,ids,context=context)
		for invl in self.browse(cr,uid,ids,context):
			if invl.source_recon_id and invl.source_recon_id.id:
				invl.source_recon_id.write()
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
			url = 'http://pickup.sicepat.com:8087/api/integration/blocksigesit?employeeno='+s
			r = requests.get(url)
			# print "===============",r.text

		return sigesit

	def get_all_unblocked_sigesit(self,cr,uid,context=None):
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
		unblocked_ids = self.pool.get('hr.employee').search(cr,uid,[('nik','not in',sigesit),('cod_position','=','sigesit')])
		for s in self.pool.get('hr.employee').browse(cr,uid,unblocked_ids):
			if s.nik:
				url = 'http://pickup.sicepat.com:8087/api/integration/unblocksigesit?employeeno='+s.nik
				r = requests.get(url)

		return unblocked_ids
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
						'invoice_line_id': inv_line.id,
						'account_analytic_id': inv_line.account_analytic_id and inv_line.account_analytic_id.id or False,
						'statement_id'	: cr_id,
					}
					cr_line_id = self.pool.get('account.bank.statement.line').create(cr,uid,cr_lines)
					inv_line.write({'cr_gesit_line':cr_line_id,'cr_gesit_id':cr_id})
		return True


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


class account_invoice_line_retur(models.TransientModel):
	_name = "account.invoice.line.retur"

	partner_id = fields.Many2one('res.partner','Partner')
	user_id = fields.Many2one('res.users',"User Responsible")
	line_ids = fields.Many2many("paket.bermasalah","account_invoice_line_retur_rel","retur_id","line_id","Invoice Lines")


