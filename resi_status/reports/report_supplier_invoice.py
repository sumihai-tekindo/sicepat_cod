from openerp.osv import osv,fields
import xlsxwriter
try:
    from cStringIO import StringIO
except ImportError:
    import StringIO
from datetime import datetime

class account_invoice(osv.osv):
	_inherit = "account.invoice"

	def print_supplier_invoice(self,cr,uid,ids,context=None):
		return {
             'type' : 'ir.actions.act_url',
             'url': '/web/custom_report?model=account.invoice&method=supplier_invoice_xls_data&data_ids=%s'%ids,
             'target': 'self',
 		}        

 	def supplier_invoice_xls_data(self,cr,uid,data_ids,context=None):
 		file_content=StringIO()
		header = ["Customer Package Number","Tracking Number","Package Price","POD Datetime","Destination","Recipient","Status","Deposit Date","Package Detail"]
		wb = xlsxwriter.Workbook(file_content,{})
		header_format = wb.add_format({'bold': True, 'align': 'center','bg_color':'yellow','border':1})
		ws = wb.add_worksheet()
		row = 0
		col = 0
		for h in header:
			ws.write(row,col,h,header_format)
			col+=1
		row+=1

		dict_status = {
			'open':'Open',
			'IN':'Barang Masuk',
			'PICKREQ':'Pick Up Request',
			'OUT':'Barang Keluar',
			'OTS':'On Transit Schedule',
			'CC':'Criss Cross',
			'CU':'CKNEE Unknown',
			'NTH':'Not At Home',
			'AU':'Antar Ulang',
			'BA':'Bad Address',
			'MR':'Misroute',
			'CODA':'Closed Once Delivery Attempt',
			'CODB':'COD Bermasalah',
			'LOST':'Barang Hilang',
			'BROKEN':'Barang Rusak',
			'RTN':'Retur ke Pusat',
			'RTS':'Retur ke Shipper',
			'RTA':'Retur ke Gerai',
			'HOLD':'Hold/Pending',
			'THP':'Resi Pihak Ketiga',
			'OSD':'On Scheduled Delivery',
			'ANT':'Dalam Pengantaran',
			'DLV':'Delivered',
			'cabang':'Delivered',
			'pusat':'Delivered',
			'submit':'Delivered',
			'approved':'Delivered',
			'paid':'Delivered'
			}
		for i in self.browse(cr,uid,data_ids,context=context):
			payment_date = False
			for p in i.payment_ids:
				d = datetime.strptime(p.date,'%Y-%m-%d')
				if not payment_date or (payment_date and d>payment_date):
					payment_date=d
			for l in i.invoice_line:
				dlv_date = l.pod_datetime
				cust_package_number=l.name
				internal_status='open'
				detail_barang = ''
				dest = l.rds_destination and l.rds_destination.name or ''
				if l.source_recon_id:
					dlv_date=l.source_recon_id.pod_datetime
					cust_package_number=l.source_recon_id.cust_package_number
					internal_status = l.source_recon_id.internal_status
					detail_barang = l.source_recon_id.detail_barang
					dest = l.source_recon_id.rds_destination and l.source_recon_id.rds_destination.name or ''
					for t in l.source_recon_id.tracking_ids:
						if t.status=='DLV':
							dlv_date=t.pod_datetime
				else:
					line_ids = self.pool.get('account.invoice.line').search(cr,uid,[('name','=',l.name),('invoice_id.type','=','out_invoice')])
					for lsource in self.pool.get('account.invoice.line').browse(cr,uid,line_ids):
						dlv_date=l.pod_datetime
						cust_package_number=lsource.cust_package_number
						internal_status=lsource.internal_status
						detail_barang=lsource.detail_barang
						dest=lsource.rds_destination.name

						for t in l.source_recon_id.tracking_ids:
							if t.status=='DLV':
								dlv_date=t.pod_datetime	
				dlv_date=datetime.strptime(dlv_date,'%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
				status = dict_status.get(internal_status,'')
				# print "===========",internal_status,status
				
				ws.write(row,0,cust_package_number or '-')
				ws.write(row,1,l.name)
				ws.write(row,2,l.price_subtotal)
				ws.write(row,3,dlv_date)
				ws.write(row,4,dest)
				ws.write(row,5,l.recipient)
				ws.write(row,6,status)
				ws.write(row,7,payment_date.strftime('%Y-%m-%d'))
				ws.write(row,8,detail_barang)
				row+=1
		wb.close()
		file_content.seek(0)
		return (file_content,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','COD_Payment_Reconciliation.xlsx')