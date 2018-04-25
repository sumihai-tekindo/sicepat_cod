from openerp.osv import osv,fields

import xlsxwriter
try:
	from cStringIO import StringIO
except ImportError:
	import StringIO
from datetime import datetime



class account_invoice_line_summary(osv.osv_memory):
	_name = "account.invoice.line.summary"


	_columns = {
		"stt_date_start"	: fields.date("Start Date",help="Tanggal awal range transaksi STT"),
		"stt_date_end"		: fields.date("End Date",help="Tanggal akhir range transaksi STT"),
		"min_weight"		: fields.date("Min. Weight",help="Min. Berat"),
		"max_weight"		: fields.date("Max. Weight",help="Max. Berat"),
		"service_type"		: fields.many2one('consignment.service.type', string="Service Type", help="Let this field empty if you want to select all service type"),
		"delivery_status"	: fields.selection([('all','All'),
										('open','Open'),
										('IN',"Barang Masuk"),
										('PICKREQ',"Pick Up Request"),
										('OUT',"Barang Keluar"),
										('OTS',"On Transit Schedule"),
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
										('THP',"Resi Pihak Ketiga"),
										('OSD',"On Scheduled Delivery"),
										('ANT',"Dalam Pengantaran"),
										('DLV',"Delivered"),
										],"Delivery Status",required=True),
		"payment_status"	: fields.selection([('all','All'),
										('cabang','Cabang'),
										('pusat','Pusat'),
										('submit','Submitted to Partner'),
										('approved','Approved By Partner'),
										('paid','Paid')],"Payment Status",required=True),


		}

	def print_report(self,cr,uid,ids,context=None):
		if not context:context={}
		ivl_pool=self.pool.get('account.invoice.line')
		ivlt_pool=self.pool.get('account.invoice.line.tracking')
		data = self.browse(cr,uid,ids[0])
		start_date=data.stt_date_start
		end_date=data.stt_date_end
		domain=[('stt_date','>=',start_date),('stt_date','<=',end_date)]
		if data.min_weight:
			domain.append(('weight','>=',data.min_weight))
		if data.max_weight:
			domain.append(('weight','<=',data.max_weight))
		if data.delivery_status!='all':
			dom_ivl_ids = ivlt_pool.search(cr,uid,[('status','=',data.delivery_status)])
			ivlt_ids = [t.invoice_line_id.id for t in ivlt_pool.browse(cr,uid,dom_ivl_ids) if t.invoice_line_id and t.invoice_line_id.id]
			domain.append(('id','in',ivlt_ids))
		if data.payment_status !='all':
			domain.append(('internal_status','='.data.payment_status))
		
		invoice_line_ids = ivl_pool.search(cr,uid,domain)

		return {
			'type' : 'ir.actions.act_url',
			'url': '/web/custom_report?model=account.invoice.line&method=print_cod_summary&data_ids=%s'%invoice_line_ids,
			'target': 'self',
			}


class account_invoice_line(osv.osv):
	_inherit = "account.invoice.line"

	def print_cod_summary(self,cr,uid,ids,context=None):

		file_content=StringIO()
		filename = "COD Summary.xlsx"
		header = ["STT","Customer Package Number","Tanggal Order","Tanggal Foto","Pengirim","Layanan",
		"Tujuan","Penerima","HP Penerima","Total COD","Lead Time","Status","POD Attempt","Penerima Barang"]

		wb = xlsxwriter.Workbook(file_content,{})
		header_format_top = wb.add_format({'bold': True, 'align': 'center','bg_color':'yellow','border':1})
		header_format = wb.add_format({'bold': True, 'align': 'center','bg_color':'yellow','border':1})
		ws = wb.add_worksheet("COD Summary Report")
		ws.write(0,0,"Sicepat Ekspres",header_format_top)
		ws.write(1,0,"COD Summary Report",header_format_top)
		
		row = 4
		col = 0
		for h in header:
			ws.write(row,col,h,header_format)
			col+=1
		row+=1
		for i in self.browse(cr,uid,ids,context=context):
			ws.write(row,0,i.name)
			ws.write(row,1,i.cust_package_number)
			ws.write(row,2,i.stt_date)
			ws.write(row,3,i.stt_date)
			ws.write(row,4,"-")
			ws.write(row,5,i.service_type.code)
			ws.write(row,6,i.rds_destination.name)
			ws.write(row,7,i.recipient)
			ws.write(row,8,"-")
			ws.write(row,9,i.price_subtotal)
			ws.write(row,10,"-")
			ws.write(row,11,i.internal_status)
			ws.write(row,12,i.pod_datetime)
			ws.write(row,13,"")
			row+=1
		wb.close()
		file_content.seek(0)
		return (file_content,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',filename)