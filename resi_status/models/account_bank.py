from openerp.osv import fields, osv
from datetime import datetime
from openerp.osv import expression
import time
from openerp.tools.translate import _



class account_bank_statement(osv.osv):
	_inherit = "account.bank.statement"
	# _name = "account.bank.statement"

	def _get_default_register_type(self,cr,uid,context=None):
		register_type = context.get('register_type',False)
		journal_type = context.get('journal_type',False)
		if register_type:
			return register_type
		else:
			if journal_type=='cash':
				return 'cr_normal'
			else:
				return 'bs_normal'
		return 'bs_normal'

	_columns = {

		"register_type" : fields.selection(
				[('bs_normal','Bank Statement'),('bs_fin','Bank Statement'),('cr_normal','Cash Register'),
				('cr_gesit','Cash Register Sigesit'),('cr_admin','Cash Register Admin')],
				string="Register Type",required=True),
		"sigesit" :fields.many2one("hr.employee","Sigesit"),
		"partner_sigesit" : fields.many2one('res.partner','Partner Sigesit'),
		"admin_receipt_id" : fields.many2one('account.bank.statement','CR Admin',ondelete='set null'),
		"admin_receipt_line_id" : fields.many2one('account.bank.statement.line','CR Line Sigesit',ondelete='set null'),
		"analytic_account_id"	: fields.many2one('account.analytic.account',"Cabang"),
		"notes": fields.text("Notes"),
		"reference_number": fields.char("Nomor Transfer"),
		"attachment": fields.binary("Bukti Transfer",
            help="File bukti transfer bank"),

		}

	_defaults = {
		"register_type":_get_default_register_type,
	}
	

	def button_confirm_bank(self, cr, uid, ids, context=None):
		if context is None:
			context = {}

		# res = super(account_bank_statement,self).button_confirm_bank(cr, uid, ids, context=context)
		
		for st in self.browse(cr, uid, ids, context=context):
			j_type = st.journal_id.type
			if not self.check_status_condition(cr, uid, st.state, journal_type=j_type):
				continue

			self.balance_check(cr, uid, st.id, journal_type=j_type, context=context)
			if (not st.journal_id.default_credit_account_id) \
					or (not st.journal_id.default_debit_account_id):
				raise osv.except_osv(_('Configuration Error!'), _('Please verify that an account is defined in the journal.'))
			for line in st.move_line_ids:
				if line.state != 'valid':
					raise osv.except_osv(_('Error!'), _('The account entries lines are not in valid state.'))
			move_ids = []
			for st_line in st.line_ids:
				counterpart_move_id = st_line.invoice_line_id and st_line.invoice_line_id.invoice_id and st_line.invoice_line_id.invoice_id.move_id or False
				counterpart_move_line_id = False
				if counterpart_move_id:
					counterpart_move_line_id = list(set([x.id for x in counterpart_move_id.line_id if x.account_id.type=='receivable']))
					if counterpart_move_line_id and counterpart_move_line_id[0]:
						counterpart_move_line_id = counterpart_move_line_id[0]
				if not st_line.amount:
					continue
				if st_line.account_id and not st_line.journal_entry_id.id:
					#make an account move as before
					if context.get('register_type','bs_normal')=='cr_gesit':
						# print "=======cr_gesit==========="
						vals = {
							'debit': st_line.amount < 0 and -st_line.amount or 0.0,
							'credit': st_line.amount > 0 and st_line.amount or 0.0,
							'account_id': st_line.account_id.id,
							'name': st_line.name,
							'counterpart_move_line_id': counterpart_move_line_id,

						}

					else:
						vals = {
						'debit': st_line.amount < 0 and -st_line.amount or 0.0,
						'credit': st_line.amount > 0 and st_line.amount or 0.0,
						'account_id': st_line.account_id.id,
						'name': st_line.name,
						'partner_id':st_line.statement_id.user_id.partner_id.id
					}
					# print "-==============",vals
					self.pool.get('account.bank.statement.line').process_reconciliation(cr, uid, st_line.id, [vals], context=context)
					invoice_line_ids = [x.id for x in st_line.invoice_line_ids]
					if context.get('register_type','bs_normal')=='cr_admin':
						self.pool.get('account.invoice.line').write(cr,uid,invoice_line_ids,{'internal_status':'cabang'})
					elif context.get('register_type','bs_normal')=='bs_fin':
						self.pool.get('account.invoice.line').write(cr,uid,invoice_line_ids,{'internal_status':'pusat'})
				elif not st_line.journal_entry_id.id:
					raise osv.except_osv(_('Error!'), _('All the account entries lines must be processed in order to close the statement.'))
				move_ids.append(st_line.journal_entry_id.id)
			if move_ids:
				self.pool.get('account.move').post(cr, uid, move_ids, context=context)
			self.message_post(cr, uid, [st.id], body=_('Statement %s confirmed, journal items were created.') % (st.name,), context=context)
		self.link_bank_to_partner(cr, uid, ids, context=context)
		return self.write(cr, uid, ids, {'state': 'confirm', 'closing_date': time.strftime("%Y-%m-%d %H:%M:%S")}, context=context)


	

class account_cash_statement(osv.osv):
	_inherit = "account.bank.statement"

	def button_confirm_cash(self, cr, uid, ids, context=None):
		res =super(account_cash_statement,self).button_confirm_bank(cr,uid,ids,context=context)
		# print "==============confirm cash2================="
		return res


