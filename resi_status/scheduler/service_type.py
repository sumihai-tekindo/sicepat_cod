from openerp import models, fields
from datetime import datetime
import psycopg2
import psycopg2.extras

from openerp.osv import expression


class ConsignmentServiceType(models.Model):
	_inherit = "consignment.service.type"

	odoo1_id = fields.Integer("Odoo1 Database ID")
	

	def fetch_service_type(self,cr,uid,context=None):
		odoo1_ids = self.pool.get('ir.config_parameter').search(cr,uid,[('key','in',['odoo1.url','odoo1.db','odoo1.db_port','odoo1.user','odoo1.password'])])
		if odoo1_ids:
			odoo1 = self.pool.get('ir.config_parameter').browse(cr,uid,odoo1_ids)
			host = ""
			db = ""
			port = ""
			user = ""
			password = ""
			for x in odoo1:
				if x.key =='odoo1.url':
					host = x.value
				elif x.key =='odoo1.db':
					db = x.value
				elif x.key =='odoo1.db_port':
					port = x.value
				elif x.key =='odoo1.user':
					user = x.value
				elif x.key =='odoo1.password':
					password = x.value
			conn_odoo1_str = "host=%s dbname=%s user=%s password=%s"%(host,db,user,password)
			# print "conn===============",conn_odoo1_str
			# print dummmmm
			conn_odoo1 = psycopg2.connect(conn_odoo1_str)
			cr_odoo1 = conn_odoo1.cursor(cursor_factory=psycopg2.extras.DictCursor)
			query_sel="""select * from consignment_service_type"""
			cr_odoo1.execute(query_sel)
			records = cr_odoo1.fetchall()

			local_ids = self.pool.get('consignment.service.type').search(cr,uid,[])
			local_service = {}
			if local_ids and local_ids!=[]:
				local = self.pool.get('consignment.service.type').browse(cr,uid,local_ids)
				for x in local:
					local_service.update({x.code:x.id})
			exists = []
			not_exists = []
			for row in records:
				d_row = dict(row)
				if d_row.get('code',False) in local_service.keys():
					exists.append(d_row)
				else:
					not_exists.append(d_row)
			for e in exists:
				value = {
					'name': e.get('name',False),
					'active': e.get('active',True),
					'code': e.get('code',False),
					'odoo1_id': e.get('id',False)
					}
				# print "==========write==========",value,local_service.get(e.get('code',False))
				self.pool.get('consignment.service.type').write(cr,uid,local_service.get(e.get('code',False)),value)

			for ne in not_exists:
				value = {
					'name': ne.get('name',False),
					'code': ne.get('code',False),
					'active': ne.get('active',True),
					'odoo1_id': ne.get('id',False)
					}
				# print "=========create===========",value
				self.pool.get('consignment.service.type').create(cr,uid,value)				
			cr_odoo1.close()
			if conn_odoo1 is not None:
				conn_odoo1.close()
			return True