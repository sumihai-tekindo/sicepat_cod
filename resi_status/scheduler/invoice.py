from openerp import models, fields
from datetime import datetime
import mysql.connector
import pymssql
from openerp.osv import expression

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

		cnx = mysql.connector.connect(**config)
		cur = cnx.cursor()
		querystt = """select s.tgltransaksi,s.pengirim,s.nostt,s.penerima,s.codNilai,coalesce(g.kode) as kode,tujuan,Layanan   
					from rudydarw_sicepat.stt s 
					left join Gerai g on s.gerai=g.id 
					where s.codNilai>0.0 and s.iscodpulled != 1 and tujuan is not NULL
					order by s.tgltransaksi asc,s.pengirim asc,s.nostt asc
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
			tgl_pengirim.update({r[2]:{'penerima':r[3],'price_unit':r[4],'asal':r[5],'tujuan':r[6],'layanan':r[7]}})
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
		
		cnx.close()
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
			query_update = """update stt set iscodpulled=1 where nostt in (%s)"""%to_update
			cnx2 = mysql.connector.connect(**config)
			cur2 = cnx2.cursor()
			cur2.execute(query_update)
			cur2.close()
			cnx2.close()

			query_pickup = """select ReceiptNumber,parcel_content,cust_package_id from PartnerRequestExt WITH (NOLOCK) where ReceiptNumber in (%s)"""%to_update
			# ss_pickup_config = {
			# 'user'		: '',
			# 'password'	: '',
			# 'host' 		: '',
			# 'database' 	: '',
			# 'port'		: '',
			# }
			pickup_conn = pymssql.connect(server=ss_pickup_config['host'], user=ss_pickup_config['user'], password=ss_pickup_config['password'], 
				port=str(ss_pickup_config['port']), database=ss_pickup_config['database'])
			cr_pickup = pickup_conn.cursor(as_dict=True)
			cr_pickup.execute(query_pickup)
			records = cr_pickup.fetchall()
			for record in records:
				detail_value = {'detail_barang':record['parcelcontent'],'cust_package_number':record['cust_package_id']}
				resi = record['ReceiptNumber']
				if invoice_dict.get(resi,False):
					self.pool.get('account.invoice.line').write(cr,uid,invoice_dict.get(resi),detail_value)
			pickup_conn.close()
		return result


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
