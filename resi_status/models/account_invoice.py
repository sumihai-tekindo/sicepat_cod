from openerp import models, fields


class account_invoice_line(models.Model):
	_inherit="account.invoice.line"

	name = fields.Char(string='No. Resi')
	recipient = fields.Char(string='Name of Recipient')
	account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
	price_cod = fields.Float(string='Price COD')
	price_package = fields.Float(string='Price Package')
	nilai_edc = fields.Char(string='nilai_EDC')
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