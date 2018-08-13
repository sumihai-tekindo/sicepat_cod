from openerp import models, fields, api 
from datetime import datetime
# import mysql.connector
import pymssql
import requests
from openerp.osv import expression

class wizard_dummy_resi(models.Model):
	_name = "wizard.dummy.resi"

	
	account_analytic_id		= fields.Many2many('account.analytic.account','analytic_id','wiz_id','analytic_wizard_dummy_rel','Current Branch Position')
	partner_id				= fields.Many2one('res.partner',"COD Customer",domain=[('customer','=',True)])
	internal_status 		= fields.Selection([
									('PICKREQ',"Pick Up Request"),
									('IN',"Barang Masuk"),
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
									],string='Internal Status')
	number_of_resi			= fields.Integer("Number of AWB per branch for selected status")	
	@api.multi
	def generate_query_pod(self,resi_number):
		query_pod = """select * from (
							SELECT  
								TR.Id as Id,
								TR.ReceiptNumber as ReceiptNumber,
								TR.TrackingType as TrackingType,
								DATEADD(hour, -7, TR.TrackingDatetime) as TrackingDatetime,
								MTS.SiteCode as SiteCode,
								MTS.Name as Name,
								NULL as CourierName,
								NULL as EmployeeNo
							FROM BOSICEPAT.POD.dbo.TrackingRecord TR WITH (NOLOCK)
							LEFT JOIN BOSICEPAT.POD.dbo.MsTrackingSite MTS WITH (NOLOCK) on TR.TrackingSiteId=MTS.Id
							where 
								TR.ReceiptNumber='%s'
							UNION
							SELECT 
								RR.Id as Id,
								RR.NoResi as ReceiptNumber,
								'ANT' as TrackingType,
								DATEADD(hour, -7, RR.ReceivedDtm) as TrackingDatetime,
								MB.BranchCodeOdoo as SiteCode,
								MB.Name as Name,
								ME.Name as CourierName,
								ME.EmployeeNo as EmployeeNo
							FROM PICKUPORDER.dbo.ReceivedResi RR WITH (NOLOCK)
							LEFT JOIN EPETTYCASH.dbo.MsBranch MB WITH (NOLOCK) on RR.BranchId=MB.Id
							LEFT JOIN PICKUPORDER.dbo.MsCourier MC WITH (NOLOCK) on RR.CourierId=MC.Id
							LEFT JOIN EPETTYCASH.dbo.MsEmployee ME WITH (NOLOCK) on MC.EmployeeId=ME.Id
							where 
								RR.NoResi='%s'
							UNION
							SELECT 
								DH.Id as Id,
								RR.NoResi as ReceiptNumber,
								CASE 
									WHEN (DH.IsProblem!='Y' ) THEN 'DLV'
									WHEN (DH.IsProblem='Y' ) THEN DP.ProblemCode
								END as TrackingType,
								DATEADD(hour, -7, DH.CompletedDtm) as TrackingDatetime,
								MB.BranchCodeOdoo as SiteCode,
								MB.Name as Name,
								ME.Name as CourierName,
								ME.EmployeeNo as EmployeeNo
							FROM PICKUPORDER.dbo.ReceivedResi RR WITH (NOLOCK)
							LEFT JOIN PICKUPORDER.dbo.DeliveryHistory DH WITH (NOLOCK) on DH.ReceivedResiId=RR.Id
							LEFT JOIN EPETTYCASH.dbo.MsBranch MB WITH (NOLOCK) on RR.BranchId=MB.Id
							LEFT JOIN PICKUPORDER.dbo.MsCourier MC WITH (NOLOCK) on RR.CourierId=MC.Id
							LEFT JOIN EPETTYCASH.dbo.MsEmployee ME WITH (NOLOCK) on MC.EmployeeId=ME.Id
							LEFT JOIN PICKUPORDER.dbo.DeliveryProblem DP WITH (NOLOCK) on DH.ProblemRemark=DP.Description
							where 
								RR.NoResi='%s' and DH.Id is not NULL
							UNION
							SELECT
								cast(STT.nostt AS int) as Id,
								STT.nostt as ReceiptNumber,
								'IN' as TrackingType,
								DATEADD(hour, -7, STT.TglFoto) as TrackingDatetime,
								MS.SiteCode as SiteCode,
								MS.Name as Name,
								NULL as CourierName,
								NULL as EmployeeNo
							FROM BOSICEPAT.POD.dbo.stt STT WITH (NOLOCK)
							LEFT JOIN BOSICEPAT.POD.dbo.MsTrackingSite MS with (nolock) on STT.gerai=MS.SiteCodeRds
							WHERE 
								STT.nostt='%s'
							UNION 
							SELECT  
								cast(TPR.ReceiptNumber AS int) as Id,
								TPR.ReceiptNumber as ReceiptNumber,
								'THP' as TrackingType,
								DATEADD(hour, -7, TPR.UploadDatetime) as TrackingDatetime,
								MTS.SiteCode as SiteCode,
								MTS.Name as Name,
								NULL as CourierName,
								NULL as EmployeeNo
							from BOSICEPAT.POD.dbo.ThirdPartyReceipt TPR WITH (NOLOCK)
							left join BOSICEPAT.POD.dbo.MsTrackingSite MTS with (nolock) on TPR.TrackingSiteId=MTS.SiteCodeRds
							where 
								TPR.ReceiptNumber='%s'
							)dummy 
							
							order by TrackingDatetime"""%(resi_number,resi_number,resi_number,resi_number,resi_number)
		return query_pod

	@api.multi
	def scheduled_tracking_note_pull(self,):
		analytic_pool = self.env['account.analytic.account']
		gesit_pool = self.env['hr.employee']
		ss_pod_ids = self.env['ir.config_parameter'].search([('key','in',['sqlpickup.url','sqlpickup.db','sqlpickup.db_port','sqlpickup.user','sqlpickup.password'])])
		ss_pod_config = {
			'user'		: '',
			'password'	: '',
			'host' 		: '',
			'database' 	: '',
			'port'		: '',
			}
		if ss_pod_ids:
			for x in ss_pod_ids:
				if x.key =='sqlpickup.url':
					ss_pod_config.update({'host' : x.value})
				elif x.key =='sqlpickup.db':
					ss_pod_config.update({'database' : x.value})
				elif x.key =='sqlpickup.user':
					ss_pod_config.update({'user' : x.value})
				elif x.key =='sqlpickup.password':
					ss_pod_config.update({'password' : x.value})
				elif x.key =='sqlpickup.db_port':
					ss_pod_config.update({'port' : x.value})
			# print "============================",ss_pod_config
			if self._context.get('to_pull',False):
				outstanding_awb_ids =self._context.get('to_pull')
			else:
				outstanding_awb_ids = self.env['account.invoice.line'].search([
					('internal_status','in',('open','IN','PICKREQ','OUT','OTS','CC','CU','NTH','AU','BA','MR','CODA','CODB','BROKEN','RTN','RTA','HOLD','OSD','ANT'))])
			# outstanding_awb_ids=[4603]
			# outstanding_awb = self.pool.get('account.invoice.line').browse(cr,uid,outstanding_awb_ids)
			# print "vvvvvvvvvvvvv",outstanding_awb_ids
			for x in outstanding_awb_ids:
				# print "x.name===========",x.name
				tn_ids = ""
				max_ids = []
				for t in x.tracking_ids:
					max_ids.append(t.sequence)
					tn_ids += str(t.tracking_note_id)+","
				tn_ids=tn_ids[:-1]
				try:
					seq_max=max(max_ids)
				except:
					seq_max=1
				add_clause = ''
				if tn_ids and tn_ids!='':
					add_clause='where Id not in (%s)'%tn_ids
				query_pod = self.generate_query_pod(x.name)
				# print "queryxxxxxxxxxxxxxxxxx",query_pod
				# ss_pod_config = {
				# 'user'		: '',
				# 'password'	: '',
				# 'host' 		: '',
				# 'database' 	: '',
				# 'port'		: '',
				# }
				pod_conn = pymssql.connect(server=ss_pod_config['host'], user=ss_pod_config['user'], password=ss_pod_config['password'], 
					port=str(ss_pod_config['port']), database=ss_pod_config['database'])
				cr_pod = pod_conn.cursor(as_dict=True)
				cr_pod.execute(query_pod)
				records = cr_pod.fetchall()
				
				isdlv = False
				existing_tracking = {}
				for t in x.tracking_ids:
					tostatus = existing_tracking.get(t.tracking_note_id,[])
					tostatus.append(t.status)
					existing_tracking.update({t.tracking_note_id:tostatus})
				# if x.id==4759:
					# print "=======existing_tracking=======",existing_tracking
				for record in records:
					# print "reccccccccccccccc",record
					if record['TrackingType'] and record['TrackingType']!="":

						analytic_id = analytic_pool.search([('code','=',record['SiteCode'])],limit=1)
						try:
							analytic_id = analytic_id[0]
						except:
							analytic_id = analytic_id
						emp_id = gesit_pool.search([('nik','=',record['EmployeeNo'])])
						try:
							emp_id = emp_id[0]
						except:
							emp_id = emp_id
						print "xxxxxxxxxxxxxxxxxxxxxxxx",analytic_id,emp_id
						detail_value = {
								'invoice_line_id':x.id,
								'sequence':seq_max,
								# 'resi_number':x.name,
								'pod_datetime':record['TrackingDatetime'],
								"position_id": analytic_id and analytic_id.id or False,
								"status": record['TrackingType'],
								"user_tracking": record['CourierName'],
								"sigesit":emp_id and emp_id.id or False,
								"tracking_note_id":record['Id'],
								}
						invl_write_value = {
							'internal_status':record['TrackingType'],
							'pod_datetime':record['TrackingDatetime'],
							'sigesit':emp_id and emp_id.id or False,
							'analytic_destination':analytic_id.id or False,
						}
						if isdlv==False and (record['Id'] not in existing_tracking.keys() or (record['Id'] in existing_tracking.keys() and record['TrackingType'] not in existing_tracking.get(record['Id']))):
							print "===",detail_value
							self.env['account.invoice.line.tracking'].create(detail_value)
							x.write(invl_write_value)
						if record['TrackingType']=='DLV':
							isdlv=True
				pod_conn.close()
		return True


	@api.multi
	def scheduled_stt_pull(self):
		self.ensure_one()
		ss_pickup_ids = self.env['ir.config_parameter'].search([('key','in',['sqlbo.url','sqlbo.db','sqlbo.db_port','sqlbo.user','sqlbo.password'])])
		ss_pickup_config = {
			'user'		: '',
			'password'	: '',
			'host' 		: '',
			'database' 	: '',
			'port'		: '',
			}
		
		if ss_pickup_ids:
			for x in ss_pickup_ids:
				if x.key =='sqlbo.url':
					ss_pickup_config.update({'host' : x.value})
				elif x.key =='sqlbo.db':
					ss_pickup_config.update({'database' : x.value})
				elif x.key =='sqlbo.user':
					ss_pickup_config.update({'user' : x.value})
				elif x.key =='sqlbo.password':
					ss_pickup_config.update({'password' : x.value})
				elif x.key =='sqlbo.db_port':
					ss_pickup_config.update({'port' : x.value})


		# print "=-=========================>",ss_pickup_ids,ss_pickup_config
		wizards = self


		for analyt in wizards.account_analytic_id:
			pickup_conn = pymssql.connect(server=ss_pickup_config['host'], user=ss_pickup_config['user'], password=ss_pickup_config['password'], 
					port=str(ss_pickup_config['port']), database=ss_pickup_config['database'])
			cur = pickup_conn.cursor(as_dict=False)
			querystt = """select  top """+str(wizards.number_of_resi)+""" 
				stt.tgltransaksi,
				stt.pengirim,
				stt.nostt, 
				stt.penerima,
				cast(right(stt.nostt,3) as bigint)*1000 as codNilai,
				ts.SiteCode as kode,
				stt.tujuan,
				stt.Layanan,
				stt.keterangan parcel_content,
				stt.nostt as cust_package_id
				from TrackingNote tn with (nolock)
				left join MsTrackingSite ts with (nolock) on tn.TrackingSiteId=ts.Id
				left join stt stt with(nolock) on tn.ReceiptNumber=stt.nostt
				where tn.TrackingType='"""+wizards.internal_status+"""' and stt.iscodpulled=0 and ts.SiteCode='"""+analyt.code+"""' 
				and stt.pengirim = '"""+wizards.partner_id.name+"""'
				order by stt.tgltransaksi asc,stt.pengirim asc,stt.nostt asc
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
			partner_cod_ids = self.env['res.partner'].search([('name','in',all_cod_cust)])
			partner_cod = {}
			if all_cod_cust and partner_cod_ids:
				for pc in partner_cod_ids:
					partner_cod.update({pc.name:pc.id})
			not_in_partner = []
			for x in all_cod_cust:
				if not partner_cod.get(x,False):
					not_in_partner.append(x)

			for nip in not_in_partner:
				# print "-----------------",nip
				if nip and nip!=None and nip !="":
					pt_id = self.env['res.partner'].create({'name':nip,'customer':True,'supplier':True,})
					partner_cod.update({nip:pt_id})

			user = self.env['res.users'].search([('id','=',self._uid)])
			partner = user.company_id.cod_customer
			domain = [('type', '=', 'sale'),
				('company_id', '=', user.company_id.id)]
			journal_id = self.env['account.journal'].search(domain, limit=1)
			rds_destination_ids = self.env['rds.destination'].search([('id','>','0')])
			rds_destination = {}
			for x in rds_destination_ids:
				rds_destination.update({x.code:x.id})

			analytic_ids = self.env['account.analytic.account'].search([('id','>','0')])
			analytic = {}		
			for x in analytic_ids:
				analytic.update({x.code:x.id})
			service_type = {}
			service_type_ids = self.env['consignment.service.type'].search([])
			for x in service_type_ids:
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
								'journal_id'	:	journal_id and journal_id[0].id,
								'invoice_type'	:	'out_invoice',
								'account_id'	:	partner.property_account_receivable.id,
								'state'			:	'draft',
								'sales_person'	:	self._uid,
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

						inv_id = self.env['account.invoice'].create(values)
						if inv_id:
							created_invoices.append(inv_id.id)

			invoice_line = self.env['account.invoice.line'].search([('invoice_id','in',created_invoices)])
			self.with_context({'to_pull':invoice_line}).scheduled_tracking_note_pull()
			# cnx.close()
			cur.close()
			to_update = ""
			invoice_dict = {}
			invoice_list = []
			for x in invoice_line:
				to_update+="'"+x.name+"',"
				invoice_dict.update({x.name:x.id})
				invoice_list.append(x.name)
			if to_update!="":
				to_update=to_update[:-1]
				print "##########################"
				print to_update
				print "##########################"

				query_update = """update POD.dbo.stt set iscodpulled=1 where nostt in (%s)"""%to_update
				cnx2 = pymssql.connect(server=ss_pickup_config['host'], user=ss_pickup_config['user'], password=ss_pickup_config['password'], 
					port=str(ss_pickup_config['port']), database=ss_pickup_config['database'])
				cur2 = cnx2.cursor()
				cur2.execute(query_update)
				cnx2.commit()
				cnx2.close()

		return True