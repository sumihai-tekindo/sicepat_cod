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
			outstanding_awb_ids = self.pool.get('account.invoice.line').search(cr,uid,[('internal_status','in',('open','IN','OUT','CC','CU','NTH','AU','BA','MR','CODA','CODB','BROKEN','RTN','RTA','HOLD'))])
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
					add_clause='and tn.Id not in (%s)'%tn_ids
				query_pod = """
					select * from (
					select tn.Id,
							tn.ReceiptNumber,
							tn.TrackingType,
							tn.TrackingDatetime,
							ts.SiteCode,
							ts.Name ,
							dh.CourierName,
							emp.EmployeeNo,
							LEAD(tn.TrackingType) over (ORDER BY tn.Id) as nexttn 
						from BOSICEPAT.POD.dbo.TrackingNote tn WITH (NOLOCK) 
						left join BOSICEPAT.POD.dbo.MsTrackingSite ts with (NOLOCK) on tn.TrackingSiteId=ts.Id
						left join PICKUPORDER.dbo.ReceivedResi rr with (NOLOCK) on tn.ReceiptNumber=rr.NoResi
						left join PICKUPORDER.dbo.DeliveryHistory dh with (nolock) on rr.Id=dh.ReceivedResiId
						left join PICKUPORDER.dbo.MsCourier cour with (nolock) on cour.Id=dh.CourierId
						left join EPETTYCASH.dbo.MsEmployee emp with (nolock) on emp.Id=cour.EmployeeId
						where tn.ReceiptNumber='%s' %s 
					) dummy_table
					where TrackingType<>coalesce(nexttn,'NONE') """%(x.name,add_clause)
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
				for record in records:
					print "reccccccccccccccc",record
					analytic_id = analytic_pool.search(cr,uid,[('code','=',record['SiteCode'])])
					try:
						analytic_id = analytic_id[0]
					except:
						analytic_id = analytic_id
					print "xxxxxxxxxxxxxxxxxxxxxxxx",record['EmployeeNo']
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
					if x.name=='000045362066':
						print "### 1 ####",detail_value
						print "### 2 ####",invl_write_value
					self.pool.get('account.invoice.line.tracking').create(cr,uid,detail_value)
					self.pool.get('account.invoice.line').write(cr,uid,x.id,invl_write_value)
				pod_conn.close()
			return True
