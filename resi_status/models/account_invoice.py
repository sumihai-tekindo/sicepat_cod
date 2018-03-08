from openerp import models, fields, api,SUPERUSER_ID, _
from datetime import datetime, timedelta
import requests
from openerp.osv import osv, expression
import mysql.connector

class account_invoice(models.Model):
	_inherit = "account.invoice"

	cod_customer = fields.Many2one('res.partner',"COD Customer",required=False)
	cod_move_id = fields.Many2one('account.move',"Journal Entry Customer COD")

	@api.multi
	def action_cancel_resi(self,):
		for inv in self:
			if inv.type=='in_invoice':
				line_ids = []
				for line in inv.invoice_line:
					if line.source_recon_id.id and line.source_recon_id.internal_status in ('submit','approved','paid'):
						line_ids.append(line.source_recon_id.id)
				if line_ids:
					lines = self.env['account.invoice.line'].search([('id','in',line_ids)])
					lines.write({'internal_status':'pusat','external_status':'new'})
		return True

	@api.multi
	def action_reopen_resi(self,):
		for inv in self:
			if inv.type=='in_invoice':
				line_ids = []
				for line in inv.invoice_line:
					if line.source_recon_id.id and line.source_recon_id.internal_status=='paid':
						line_ids.append(line.source_recon_id.id)
				if line_ids:
					lines = self.env['account.invoice.line'].search([('id','in',line_ids)])
					lines.write({'internal_status':'approved','external_status':'accepted'})
		return True

	@api.multi
	def invoice_validate(self):
		res = super(account_invoice,self).invoice_validate()
		for inv in self:
			if inv.type=='in_invoice':
				line_ids = []
				for line in inv.invoice_line:
					if line.source_recon_id.id and line.source_recon_id.internal_status=='submit':
						line_ids.append(line.source_recon_id.id)
				if line_ids:
					lines = self.env['account.invoice.line'].search([('id','in',line_ids)])
					lines.write({'internal_status':'approved','external_status':'accepted'})
		return res

	@api.multi
	def confirm_paid(self):
		res = super(account_invoice,self).confirm_paid()
		for inv in self:
			if inv.type=='in_invoice':
				line_ids = []
				for line in inv.invoice_line:
					if line.source_recon_id.id and line.source_recon_id.internal_status=='approved':
						line_ids.append(line.source_recon_id.id)
				if line_ids:
					lines = self.env['account.invoice.line'].search([('id','in',line_ids)])
					lines.write({'internal_status':'paid','external_status':'reconciled'})
		return res

	
	@api.model
	def line_get_convert_cod(self, line, part, date,company_id):
		#print "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",company_id.cod_accrue_account_id.id or False
		return {
			'date_maturity': line.get('date_maturity', False),
			'partner_id': part,
			'name': line['name'][:64],
			'date': date,
			'debit': line['price']>0 and line['price'],
			'credit': line['price']<0 and -line['price'],
			'account_id': line['price']< 0 and company_id.cod_accrue_account_id.id or company_id.account_temp_1.id or False,
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
	def _get_analytic_lines_cod(self):
		""" Return a list of dict for creating analytic lines for self[0] """
		company_currency = self.company_id.currency_id
		sign = 1 if self.type in ('out_invoice', 'in_refund') else -1

		iml = self.env['account.invoice.line'].move_line_get_cod(self.id)
		for il in iml:
			#print "==========account_idaccount_id========",il['account_id']
			if il['account_analytic_id']:
				if self.type in ('in_invoice', 'in_refund'):
					ref = self.reference
				else:
					ref = self.number
				if not self.journal_id.analytic_journal_id:
					raise except_orm(_('No Analytic Journal!'),
						_("You have to define an analytic journal on the '%s' journal!") % (self.journal_id.name,))
				currency = self.currency_id.with_context(date=self.date_invoice)
				il['analytic_lines'] = [(0,0, {
					'name': il['name'],
					'date': self.date_invoice,
					'account_id': il['account_analytic_id'],
					'unit_amount': il['quantity'],
					'amount': currency.compute(il['price'], company_currency) * sign,
					'product_id': il['product_id'],
					'product_uom_id': il['uos_id'],
					'general_account_id': il['account_id'],
					'journal_id': self.journal_id.analytic_journal_id.id,
					'ref': ref,
				})]
		return iml

	@api.multi
	def action_move_create_cod(self):
		""" Creates invoice related analytics and financial move lines for COD Customer"""
		account_invoice_tax = self.env['account.invoice.tax']
		account_move = self.env['account.move']

		for inv in self:
			if inv.type in ('in_invoice', 'in_refund'):
				continue

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
			iml = inv._get_analytic_lines_cod()
			print "!!!!!!!!!!!!!!!!!!!!!!!!!",iml
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
			# print "------------",iml
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
						'account_id': inv.company_id.account_temp_1.id, #perbaiki disini
						'date_maturity': t[0],
						'amount_currency': diff_currency and amount_currency,
						'currency_id': diff_currency and inv.currency_id.id,
						'ref': ref,
					})
				# print "$$$$$$$$$ 1 $$$$$$$$$$",iml
			else:
				# print "\nxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
				print inv.company_id.account_temp_1.id
				# print "\nxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n"
				iml.append({
					'type': 'dest',
					'name': name,
					'price': total,
					'account_id': inv.company_id.account_temp_1.id, #perbaiki disini,
					'date_maturity': inv.date_due,
					'amount_currency': diff_currency and total_currency,
					'currency_id': diff_currency and inv.currency_id.id,
					'ref': ref,
				})
				# print "$$$$$$$$$ 2 $$$$$$$$$$",iml
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


	
class account_invoice_line_payment_type(models.Model):
	_name = "acc.invoice.line.pt"

	name = fields.Char(string='Payment Type Name')
	code = fields.Char(string='Payment Type Code')

class account_invoice_line_tracking(models.Model):
	_name = "account.invoice.line.tracking"

	_order = "pod_datetime asc, tracking_note_id asc, sequence asc"

	invoice_line_id = fields.Many2one("account.invoice.line","Tracking ID")
	sequence = fields.Integer("Sequence")
	resi_number = fields.Char(related='invoice_line_id.name',string="Resi Number",store=True)
	pod_datetime = fields.Datetime("POD Datetime")
	position_id = fields.Many2one("account.analytic.account","Tracking Position")
	status = fields.Char("Tracking Status")
	user_tracking = fields.Char("User Tracking")
	sigesit = fields.Many2one("hr.employee","Sigesit")
	notes	= fields.Text("Remarks")
	tracking_note_id = fields.Integer("Tracking Note ID")


class account_invoice_line(models.Model):
	_inherit="account.invoice.line"

	@api.one
	@api.depends('analytic_destination')
	def _compute_users(self):
		if self.analytic_destination:
			user_ids = self.env['res.users'].sudo().search([('analytic_id','=',self.analytic_destination.id)])
			self.user_ids = user_ids

	cod_customer= fields.Many2one(relation="res.partner",related='invoice_id.cod_customer',string="Resi Number",store=True)
	name = fields.Char(string='No. Resi')
	recipient = fields.Char(string='Name of Recipient')
	price_cod = fields.Float(string='Price COD')
	price_package = fields.Float(string='Price Package')
	nilai_edc = fields.Char(string='Nilai EDC')
	pod_datetime = fields.Datetime(string='POD Datetime')
	sigesit = fields.Many2one('hr.employee',string='Sigesit')
	payment_type = fields.Many2one('acc.invoice.line.pt',string='Payment Type')
	internal_status = fields.Selection([('open','Open'),
										('IN',"Barang Masuk"),
										('PICKREQ',"Pick Up Request"),
										('OUT',"Barang Keluar"),
										('CC',"Criss Cross"),
										('CU',"CKNEE Unknown"),
										('NTH',"Not At Home"),
										('AU',"Antar Ulang"),
										('BA',"Bad Address"),
										('MR',"Misroute"),
										('CODA',"Closed Once Delivery Attempt"),
										('CODB',"COD Bermasalah"),
										('LOST',"Barang Hilang"),
										('BROKEN',"Barang Rusak"),
										('RTN',"Retur ke Pusat"),
										('RTS',"Retur ke Shipper"),
										('RTA',"Retur ke Gerai"),
										('HOLD',"Hold/Pending"),
										('ANT',"Dalam Pengantaran"),
										('DLV',"Delivered"),
										('cabang','Cabang'),
										('pusat','Pusat'),
										('submit','Submitted to Partner'),
										('approved','Approved By Partner'),
										('paid','Paid')],string='Internal Status')
	external_status = fields.Selection([('new','New'),
										('submitted','Submitted'),
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
	source_recon_id = fields.Many2one('account.invoice.line',"Reconciliation AWB Source",ondelete="set null")
	rds_destination = fields.Many2one('rds.destination',"RDS Destination")
	analytic_destination = fields.Many2one('account.analytic.account',"Current Position Branch")
	tracking_ids = fields.One2many('account.invoice.line.tracking','invoice_line_id',"Tracking Lines")
	service_type = fields.Many2one('consignment.service.type', string='Service Type')
	detail_barang = fields.Text("Detail Barang")
	cust_package_number=fields.Text("Customer Package Number")
	user_ids = fields.Many2many('res.users',string='Users', store=True, readonly=True, compute='_compute_users')
	stt_date = fields.Date('Tanggal Transaksi STT',related='invoice_id.date_invoice')

	def get_last_tracking(self,cr,uid,ids,context=None):
		if not context:context={}
		last_tracking = False
		if ids:
			for x in self.pool.get('account.invoice.line').browse(cr,uid,ids,context=context):
				for y in x.tracking_ids:
					last_tracking = y.user_tracking
		return last_tracking

	def getuser(self,cr,uid,ids,context=None):
		if not context:context={}
		user = self.pool.get('res.users').browse(cr,uid,uid)
		return user.name

	def get_last_sigesit(self,cr,uid,ids,info='sigesit',context=None):
		if not context:context={}
		last_sigesit = False
		last_date = False
		if ids:
			for x in self.pool.get('account.invoice.line').browse(cr,uid,ids,context=context):
				for y in x.tracking_ids:
					if y.sigesit:
						last_sigesit = y.sigesit.name
						last_date = y.pod_datetime
		# print "============",last_sigesit
		return info=='sigesit' and last_sigesit or last_date

	def get_last_position(self,cr,uid,ids,context=None):
		if not context:context={}
		last_position = False
		if ids:
			for x in self.pool.get('account.invoice.line').browse(cr,uid,ids,context=context):
				for y in x.tracking_ids:
					last_position = y.user_tracking
		return last_position

	@api.model
	def move_line_get_item_cod(self, line):
		return {
			'type': 'src',
			'name': line.name.split('\n')[0][:64],
			'price_unit': line.price_unit,
			'quantity': line.quantity,
			'price': line.price_subtotal,
			'account_id': line.invoice_id.company_id.cod_accrue_account_id.id,
			'product_id': line.product_id.id,
			'uos_id': line.uos_id.id,
			'account_analytic_id': line.account_analytic_id.id,
			'taxes': line.invoice_line_tax_id,
		}

	@api.model
	def move_line_get_cod(self, invoice_id):
		inv = self.env['account.invoice'].browse(invoice_id)
		currency = inv.currency_id.with_context(date=inv.date_invoice)
		company_currency = inv.company_id.currency_id

		res = []
		for line in inv.invoice_line:
			mres = self.move_line_get_item_cod(line)
			mres['invl_id'] = line.id
			res.append(mres)
			tax_code_found = False
			taxes = line.invoice_line_tax_id.compute_all(
				(line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)),
				line.quantity, line.product_id, inv.partner_id)['taxes']
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
		#print "###########################"
		#print res
		#print "###########################"
		return res
		
	# def unlink(self,cr,uid,ids,context=None):
	# 	if not context:context={}
	# 	res = super(account_invoice_line,self).unlink(cr,uid,ids,context=context)
	# 	for invl in self.browse(cr,uid,ids,context):
	# 		if invl.source_recon_id and invl.source_recon_id.id:
	# 			invl.source_recon_id.write({'invlso'})

	def package_returned(self,cr,uid,ids,context=None):
		if not context:context={}
		invlt_pool = self.pool.get('account.invoice.line.tracking')
		if ids:
			user = self.pool.get('res.users').browse(cr,uid,uid)
			for x in self.pool.get('account.invoice.line').browse(cr,SUPERUSER_ID,ids,context=context):
				self.pool.get('account.invoice.line').write(cr,SUPERUSER_ID,ids,{
					'sigesit':False,
					'internal_status':'IN',
					'pod_datetime':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
					"analytic_destination":user.analytic_id and user.analytic_id.id or False
					})
				max_invl_id_track_sequence = 0
				if x.tracking_ids:
					max_invl_id_track_sequence = max([a.sequence for a in x.tracking_ids])
				#print "==============",x.id,x.name
				tracking_value = {
					"invoice_line_id": x.id,
					"sequence": max_invl_id_track_sequence+1 ,
					# "resi_number": x.name,
					"pod_datetime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
					"position_id": user.analytic_id and user.analytic_id.id or False,
					"status": 'IN',
					"user_tracking": user.name,
					"sigesit": False,
				}
				invlt_pool.create(cr,SUPERUSER_ID,tracking_value)
		return True
		
	
	


class account_journal(models.Model):
	_inherit = "account.journal"

	cod_user_responsible = fields.Many2many('res.users', 'account_journal_res_users_rel', 'journal_id', 'user_id', string='COD Responsibles' )
	cod_admin_user = fields.Many2many('res.users', 'account_journal_admin_res_users_rel', 'journal_id', 'user_id', string='COD Admin Responsibles' )





