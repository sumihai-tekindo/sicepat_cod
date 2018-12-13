from openerp import models, fields
from datetime import datetime
import mysql.connector
import pymssql
import requests
from openerp.osv import expression

class account_invoice_line(models.Model):
	_inherit = "account.invoice.line"

	uploaded_status = fields.Selection([('open','Open'),
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
										('force_close','Forced as Close'),
										('cabang','Cabang'),
										('pusat','Pusat'),
										('submit','Submitted to Partner'),
										('approved','Approved By Partner'),
										('paid','Paid')],string='Internal Status')


	def upload_status_stt(self,cr,uid,context=None):
		if not context:
			context={}
		# stt_ids = self.pool.get('account.invoice.line').search(cr,uid,[('uploaded_status','=',)])
		query="select ail.id,ail.name,ail.internal_status \
			from account_invoice_line ail \
			left join account_invoice ai on ail.invoice_id=ai.id \
			where ai.type='out_invoice' and ail.internal_status!=coalesce(ail.uploaded_status,'') and ai.state!='cancel'"
		cr.execute(query)
		res =cr.dictfetchall()
		# result = {}

		ss_bosicepat_ids = self.pool.get('ir.config_parameter').search(cr,uid,[('key','in',['sqlbo.url','sqlbo.db','sqlbo.db_port','sqlbo.user','sqlbo.password'])])
		ss_bosicepat_config = {
			'user'		: '',
			'password'	: '',
			'host' 		: '',
			'database' 	: '',
			'port'		: '',
			}
		if ss_bosicepat_ids:
			ss_pickup2 = self.pool.get('ir.config_parameter').browse(cr,uid,ss_bosicepat_ids)
			for x in ss_pickup2:
				if x.key =='sqlbo.url':
					ss_bosicepat_config.update({'host' : x.value})
				elif x.key =='sqlbo.db':
					ss_bosicepat_config.update({'database' : x.value})
				elif x.key =='sqlbo.user':
					ss_bosicepat_config.update({'user' : x.value})
				elif x.key =='sqlbo.password':
					ss_bosicepat_config.update({'password' : x.value})
				elif x.key =='sqlbo.db_port':
					ss_bosicepat_config.update({'port' : x.value})
		cnx2 = pymssql.connect(server=ss_bosicepat_config['host'], user=ss_bosicepat_config['user'], password=ss_bosicepat_config['password'], 
				port=str(ss_bosicepat_config['port']), database=ss_bosicepat_config['database'])
		cur2 = cnx2.cursor()
		
		result=[]
		for r in res:
			query_update ="update POD.dbo.stt set codstatus='%s' where nostt='%s';"%(r['internal_status'],r['name'])
			# print "-----------",query_update,"\n"
			result.append(query_update)
			x=cur2.execute(query_update)
			y=cnx2.commit()
			if cur2.rowcount==1 :
				self.pool.get('account.invoice.line').write(cr,uid,r['id'],{'uploaded_status':r['internal_status']})
		cnx2.close()
		return result



class account_invoice(models.Model):
	_inherit = "account.invoice"

	def scheduled_stt_pull(self,cr,uid,context=None):
		odoo1_ids = self.pool.get('ir.config_parameter').search(cr,uid,[('key','in',['mysql.url','mysql.db','mysql.db_port','mysql.user','mysql.password'])])
		config = {
			'user'		: '',
			'password'	: '',
			'host' 		: '',
			'database' 	: '',
			'raise_on_warnings':True,
			}
		if odoo1_ids:
			odoo1 = self.pool.get('ir.config_parameter').browse(cr,uid,odoo1_ids)
			for x in odoo1:
				if x.key =='mysql.url':
					config.update({'host' : x.value})
				elif x.key =='mysql.db':
					config.update({'database' : x.value})
				elif x.key =='mysql.user':
					config.update({'user' : x.value})
				elif x.key =='mysql.password':
					config.update({'password' : x.value})
		
		ss_pickup_ids = self.pool.get('ir.config_parameter').search(cr,uid,[('key','in',['sqlpickup.url','sqlpickup.db','sqlpickup.db_port','sqlpickup.user','sqlpickup.password'])])
		ss_pickup_config = {
			'user'		: '',
			'password'	: '',
			'host' 		: '',
			'database' 	: '',
			'port'		: '',
			}

		
		if ss_pickup_ids:
			ss_pickup = self.pool.get('ir.config_parameter').browse(cr,uid,ss_pickup_ids)
			for x in ss_pickup:
				if x.key =='sqlpickup.url':
					ss_pickup_config.update({'host' : x.value})
				elif x.key =='sqlpickup.db':
					ss_pickup_config.update({'database' : x.value})
				elif x.key =='sqlpickup.user':
					ss_pickup_config.update({'user' : x.value})
				elif x.key =='sqlpickup.password':
					ss_pickup_config.update({'password' : x.value})
				elif x.key =='sqlpickup.db_port':
					ss_pickup_config.update({'port' : x.value})


		ss_bosicepat_ids = self.pool.get('ir.config_parameter').search(cr,uid,[('key','in',['sqlbo.url','sqlbo.db','sqlbo.db_port','sqlbo.user','sqlbo.password'])])
		ss_bosicepat_config = {
			'user'		: '',
			'password'	: '',
			'host' 		: '',
			'database' 	: '',
			'port'		: '',
			}
		if ss_bosicepat_ids:
			ss_pickup2 = self.pool.get('ir.config_parameter').browse(cr,uid,ss_bosicepat_ids)
			for x in ss_pickup2:
				if x.key =='sqlbo.url':
					ss_bosicepat_config.update({'host' : x.value})
				elif x.key =='sqlbo.db':
					ss_bosicepat_config.update({'database' : x.value})
				elif x.key =='sqlbo.user':
					ss_bosicepat_config.update({'user' : x.value})
				elif x.key =='sqlbo.password':
					ss_bosicepat_config.update({'password' : x.value})
				elif x.key =='sqlbo.db_port':
					ss_bosicepat_config.update({'port' : x.value})

		pickup_conn = pymssql.connect(server=ss_pickup_config['host'], user=ss_pickup_config['user'], password=ss_pickup_config['password'], 
				port=str(ss_pickup_config['port']), database=ss_pickup_config['database'])
		cur = pickup_conn.cursor(as_dict=False)
		querystt = """select 
			stt.tgltransaksi,
			part.Name as pengirim,
			stt.nostt, 
			pre.recipient_name as penerima,
			coalesce(pre.cod_value,stt.codNilai) as codNilai,
			mts.SiteCode as kode,
			stt.tujuan,
			stt.Layanan,
			pre.parcel_content,
			pre.cust_package_id
			from
			PICKUPORDER.dbo.PartnerRequestExt pre with (nolock)
			left join PICKUPORDER.dbo.PartnerRequest req with (nolock) on req.Id=pre.PartnerRequestId
			left join PICKUPORDER.dbo.Partners part with (nolock) on part.Id=req.PartnerId
			left join BOSICEPAT.POD.dbo.stt stt with (nolock) on stt.nostt=pre.ReceiptNumber
			left join BOSICEPAT.POD.dbo.MsTrackingSite mts with (nolock) on mts.SiteCodeRds=stt.gerai
			where (pre.cod_value >0.0 or stt.codNilai>0)  and stt.tgltransaksi >='2018-05-30 00:00:00' and (stt.iscodpulled is NULL or stt.iscodpulled=0)
			UNION
			select 
			stt.tgltransaksi,
			stt.pengirim,
			stt.nostt, 
			stt.penerima as penerima,
			stt.codNilai as codNilai,
			mts.SiteCode as kode,
			stt.tujuan,
			stt.Layanan,
			'-' as parcel_content,
			'-' as cust_package_id
			from 
			BOSICEPAT.POD.dbo.stt stt with (nolock) 
			left join BOSICEPAT.POD.dbo.MsTrackingSite mts with (nolock) on mts.SiteCodeRds=stt.gerai
			left join PICKUPORDER.dbo.PartnerRequestExt pre with (nolock) on stt.nostt=pre.ReceiptNumber
			where stt.asal='BKI10000' and stt.codNilai>=5000 and stt.tgltransaksi>'2018-05-30 00:00:00' 
			and (stt.iscodpulled is NULL or stt.iscodpulled=0) and stt.pengirim <> 'Lazada Indonesia' and stt.nostt <> pre.ReceiptNumber
			order by stt.tgltransaksi asc,pengirim asc,stt.nostt asc
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
			# print "-----------------",r
			data_tgl = data.get(r[0],{})
			tgl_pengirim = data_tgl.get(r[1],{})
			all_cod_cust.append(r[1])
			tgl_pengirim.update({r[2]:{'penerima':r[3],'price_unit':r[4],'asal':r[5],'tujuan':r[6],'layanan':r[7],'parcel_content':r[8],'cust_package_id':r[9]}})
			data_tgl.update({r[1]:tgl_pengirim})
			data.update({r[0]:data_tgl})
		# print "======================",data
		all_cod_cust = list(set(all_cod_cust))
		all_cod_cust = [x.encode("utf-8") for x in all_cod_cust]
		# print "===============",all_cod_cust
		partner_cod_ids = self.pool.get('res.partner').search(cr,uid,[('name','in',all_cod_cust)])
		partner_cod = {}
		if all_cod_cust and partner_cod_ids:
			for pc in self.pool.get('res.partner').browse(cr,uid,partner_cod_ids):
				partner_cod.update({pc.name:pc.id})
		not_in_partner = []
		for x in all_cod_cust:
			if not partner_cod.get(x,False):
				not_in_partner.append(x)

		for nip in not_in_partner:
			# print "-----------------",nip
			if nip and nip!=None and nip !="":
				pt_id = self.pool.get('res.partner').create(cr,uid,{'name':nip,'customer':True,'supplier':True,})
				partner_cod.update({nip:pt_id})

		user = self.pool.get('res.users').browse(cr,uid,uid,context=context)
		partner = user.company_id.cod_customer
		domain = [('type', '=', 'sale'),
			('company_id', '=', user.company_id.id)]
		journal_id = self.pool.get('account.journal').search(cr,uid,domain, limit=1)
		rds_destination_ids = self.pool.get('rds.destination').search(cr,uid,[],context=context)
		rds_destination = {}
		for x in self.pool.get('rds.destination').browse(cr,uid,rds_destination_ids):
			rds_destination.update({x.code:x.id})

		analytic_ids = self.pool.get('account.analytic.account').search(cr,uid,[],context=context)
		analytic = {}		
		for x in self.pool.get('account.analytic.account').browse(cr,uid,analytic_ids):
			analytic.update({x.code:x.id})
		service_type = {}
		service_type_ids = self.pool.get('consignment.service.type').search(cr,uid,[],context=context)
		for x in self.pool.get('consignment.service.type').browse(cr,uid,service_type_ids):
			service_type.update({x.code:x.id})
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
								'name'					:	awb,
								'account_id'			:	user.company_id.account_temp_1.id,
								'price_unit'			:	awbs.get(awb).get('price_unit',0.0),
								'recipient'				:	awbs.get(awb).get('penerima',0.0),
								'price_package'			:	awbs.get(awb).get('price_unit',0.0),
								'detail_barang'			:	awbs.get(awb).get('parcel_content',0.0),
								'cust_package_number'	:	awbs.get(awb).get('cust_package_id',0.0),
								'account_analytic_id'	:	analytic.get(awbs.get(awb).get('asal',0.0)),
								'internal_status'		:	'open',
								'rds_destination'		: 	rds_destination.get(awbs.get(awb).get('tujuan',0.0)),
								'service_type'			: 	service_type.get(awbs.get(awb).get('layanan',0.0)),
							}
							invoice_line.append((0,0,lines))
					values.update({'invoice_line':invoice_line})

					inv_id = self.pool.get('account.invoice').create(cr,uid,values)
					if inv_id:
						created_invoices.append(inv_id)
		invoice_line = self.pool.get('account.invoice.line').search(cr,uid,[('invoice_id','in',created_invoices)])
		
		# cnx.close()
		cur.close()
		to_update = ""
		invoice_dict = {}
		invoice_list = []
		for x in self.pool.get('account.invoice.line').browse(cr,uid,invoice_line):
			to_update+="'"+x.name+"',"
			invoice_dict.update({x.name:x.id})
			invoice_list.append(x.name)
		if to_update!="":
			to_update=to_update[:-1]
			query_update = """update POD.dbo.stt set iscodpulled=1 where nostt in (%s)"""%to_update
			cnx2 = pymssql.connect(server=ss_bosicepat_config['host'], user=ss_bosicepat_config['user'], password=ss_bosicepat_config['password'], 
				port=str(ss_bosicepat_config['port']), database=ss_bosicepat_config['database'])
			cur2 = cnx2.cursor()
			cur2.execute(query_update)
			# cnx2.commit()
			cnx2.close()

		return True


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
			url = 'http://pickup.sicepat.com:8082/api/integration/blocksigesit?employeeno='+s
			r = requests.get(url)
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
				url = 'http://pickup.sicepat.com:8082/api/integration/unblocksigesit?employeeno='+s.nik
				r = requests.get(url)

		return unblocked_ids
