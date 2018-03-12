from openerp import models, fields
from datetime import datetime
import mysql.connector
import pymssql
from openerp.osv import expression

class account_invoice(models.Model):
	_inherit = "account.invoice"

	def scheduled_tracking_note_pull(self,cr,uid,context=None):
		analytic_pool = self.pool.get('account.analytic.account')
		gesit_pool = self.pool.get('hr.employee')
		ss_pod_ids = self.pool.get('ir.config_parameter').search(cr,uid,[('key','in',['sqlpickup.url','sqlpickup.db','sqlpickup.db_port','sqlpickup.user','sqlpickup.password'])])
		ss_pod_config = {
			'user'		: '',
			'password'	: '',
			'host' 		: '',
			'database' 	: '',
			'port'		: '',
			}
		if ss_pod_ids:
			ss_pod = self.pool.get('ir.config_parameter').browse(cr,uid,ss_pod_ids)
			for x in ss_pod:
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
			outstanding_awb_ids = self.pool.get('account.invoice.line').search(cr,uid,[('internal_status','in',('open','IN','PICKREQ','OUT','CC','CU','NTH','AU','BA','MR','CODA','CODB','BROKEN','RTN','RTA','HOLD'))])
			outstanding_awb = self.pool.get('account.invoice.line').browse(cr,uid,outstanding_awb_ids)
			# print "vvvvvvvvvvvvv",outstanding_awb_ids
			for x in outstanding_awb:
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
							where TR.ReceiptNumber='%s'
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
							where RR.NoResi='%s'
							UNION
							SELECT 
							RR.Id as Id,
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
							where RR.NoResi='%s'
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
							LEFT JOIN BOSICEPAT.POD.dbo.MsTrackingSite MS on STT.gerai=MS.SiteCodeRds
							WHERE STT.nostt='%s'
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
							where TPR.ReceiptNumber='%s'
							)dummy 
							%s
							order by TrackingDatetime"""%(x.name,x.name,x.name,x.name,x.name,add_clause)
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
				for record in records:
					# print "reccccccccccccccc",record
					analytic_id = analytic_pool.search(cr,uid,[('code','=',record['SiteCode'])])
					try:
						analytic_id = analytic_id[0]
					except:
						analytic_id = analytic_id
					# print "xxxxxxxxxxxxxxxxxxxxxxxx",record['EmployeeNo']
					emp_id = gesit_pool.search(cr,uid,[('nik','=',record['EmployeeNo'])],context={})
					try:
						emp_id = emp_id[0]
					except:
						emp_id = emp_id
					detail_value = {
							'invoice_line_id':x.id,
							'sequence':seq_max,
							# 'resi_number':x.name,
							'pod_datetime':record['TrackingDatetime'],
							"position_id": analytic_id or False,
							"status": record['TrackingType'],
							"user_tracking": record['CourierName'],
							"sigesit": emp_id or False,
							"tracking_note_id":record['Id'],
							}
					invl_write_value = {
						'internal_status':record['TrackingType'],
						'pod_datetime':record['TrackingDatetime'],
						'sigesit':emp_id or False,
						'analytic_destination':analytic_id or False,
					}
					if isdlv==False:
						self.pool.get('account.invoice.line.tracking').create(cr,uid,detail_value)
						self.pool.get('account.invoice.line').write(cr,uid,x.id,invl_write_value)
					if record['TrackingType']=='DLV':
						isdlv=True
				pod_conn.close()
		return True
