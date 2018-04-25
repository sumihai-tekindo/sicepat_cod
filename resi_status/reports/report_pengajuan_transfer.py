from openerp.osv import osv,fields

import xlsxwriter
try:
	from cStringIO import StringIO
except ImportError:
	import StringIO
from datetime import datetime

class account_voucher_picker(osv.osv_memory):
	_name = "account.voucher.picker"

	_columns = {
		"line_ids": fields.many2many("account.voucher","account_voucher_picker_rel","picker_id","line_id","Voucher Payments")
	}

	def default_get(self, cr, uid, fields, context=None):
		res = super(account_voucher_picker,self).default_get(cr,uid,fields,context=context)
		res.update({
			'line_ids':context.get('active_ids',False),
			})
		return res

	def print_report_voucher(self,cr,uid,ids,context=None):
		if not context:context={}
		for picker in self.browse(cr,uid,ids,context=context):
			voucher_ids =[]
			for vouch in picker.line_ids:
				voucher_ids.append(vouch.id)
		return self.pool.get('account.voucher').print_pengajuan_transfer(cr,uid,voucher_ids,context=context)

class account_voucher(osv.osv):
	_inherit = "account.voucher"

	def print_pengajuan_transfer(self,cr,uid,ids,context=None):
		return {
			'type' : 'ir.actions.act_url',
			'url': '/web/custom_report?model=account.voucher&method=pengajuan_transfer&data_ids=%s'%ids,
			'target': 'self',
			}

	def pengajuan_transfer(self,cr,uid,ids,context=None):
		voucher = self.pool.get('account.voucher').browse(cr,uid,ids,context=context)
		date = voucher and voucher[0].date
		dt_format = datetime.strptime(date,'%Y-%m-%d').strftime('%d %B %Y')
		file_content=StringIO()
		filename = "Rekap Pengeluaran %s.xlsx" %(dt_format)
		header = ["Tanggal","Bank","Account","Atas Nama","Nomor","Keterangan"]

		wb = xlsxwriter.Workbook(file_content,{})
		header_format_top = wb.add_format({'bold': True, 'align': 'center','bg_color':'yellow','border':1})
		header_format = wb.add_format({'bold': True, 'align': 'center','bg_color':'yellow','border':1})
		sheets = [v.journal_id for v in voucher] 
		sheets = list(set(sheets))
		sheet_dict =  dict.fromkeys(sheets, [])
		for vx in voucher:
			current = sheet_dict.get(vx.journal_id)
			current.append(vx.id)
			sheet_dict.update({vx.journal_id:current})
		for s in sheets:
		
			ws = wb.add_worksheet(s.name)
			ws.write(0,0,"Sicepat Ekspres",header_format_top)
			ws.write(1,0,"Laporan Pengajuan Pengeluaran Bank",header_format_top)
			ws.write(2,0,date,header_format_top)
			
			row = 4
			col = 0
			for h in header:
				ws.write(row,col,h,header_format)
				col+=1
			row+=1
			for v in self.browse(cr,uid,sheet_dict.get(s,[]),context=context):
				v_date = datetime.strptime(v.date,'%Y-%m-%d').strftime('%Y-%m-%d')
				bank_name = v.partner_id.bank_ids and v.partner_id.bank_ids[0].bank_name or ''
				acc_number = v.partner_id.bank_ids and v.partner_id.bank_ids[0].acc_number or ''
				acc_owner = v.partner_id.bank_ids and v.partner_id.bank_ids[0].owner_name or ''
				for vline in v.line_dr_ids:
					if vline.reconcile==True and vline.amount>0:
						ws.write(row,0,v_date)
						ws.write(row,1,bank_name)
						ws.write(row,2,acc_number)
						ws.write(row,3,acc_owner)
						ws.write(row,4,vline.move_line_id.ref)
						ws.write(row,5,vline.move_line_id.name =='/' and 'Pembayaran COD ke Lazada' or vline.name)
						row+=1
		wb.close()
		file_content.seek(0)
		return (file_content,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',filename)