from openerp import models, fields
from datetime import datetime

class res_company(models.Model):
	_inherit="res.company"

	account_temp_1			= fields.Many2one('account.account',"Temp Account Invoice")
	account_temp_2			= fields.Many2one('account.account',"Temp Account Cabang")
	cod_accrue_account_id 	= fields.Many2one('account.account',"Temp Acc. Accrual Liability Cust.Inv")
	cod_accrue_journal_id 	= fields.Many2one('account.journal',"Temp Acc. Accrual Journal Cust.Inv")

class hr_employee(models.Model):
	_inherit = "hr.employee"

	account_cash_cod = fields.Many2one('account.account',"Sigesit Account")
	nik = fields.Char("NIK")
