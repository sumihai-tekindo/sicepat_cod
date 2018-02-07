from openerp import models, fields
from datetime import datetime
import psycopg2
import psycopg2.extras

from openerp.osv import expression

class hr_employee(models.Model):
	_inherit = "hr.employee"

	odoo1_id = fields.Integer("Odoo1 ID")

	def fetch_employee(self,cr,uid,context=None):
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
			query_sel="""select * from hr_employee where cod_position is not NULL and active=True """
			cr_odoo1.execute(query_sel)
			records = cr_odoo1.fetchall()

			local_ids = self.pool.get('hr.employee').search(cr,uid,[('cod_position','!=',False)])
			local_employee = {}
			if local_ids and local_ids!=[]:
				local = self.pool.get('hr.employee').browse(cr,uid,local_ids)
				for x in local:
					local_employee.update({x.nik:x.id})
			exists = []
			not_exists = []
			for row in records:
				d_row = dict(row)
				if d_row.get('nik',False) in local_employee.keys():
					exists.append(d_row)
				else:
					not_exists.append(d_row)
			for e in exists:
				value = {
					'name': e.get('name_related',False),
					'nik' : e.get('nik',False),
					'cod_position': e.get('cod_position',False),
					'active': e.get('active',True),
					'odoo1_id': e.get('id',False)
					}
				# print "==========write==========",value,local_employee.get(e.get('code',False))
				self.pool.get('hr.employee').write(cr,uid,local_employee.get(e.get('code',False)),value)

			for ne in not_exists:
				value = {
					'name': ne.get('name_related',False),
					'nik' : ne.get('nik',False),
					'cod_position': ne.get('cod_position',False),
					'active': ne.get('active',True),
					'odoo1_id': ne.get('id',False)
					}
				# print "=========create===========",value
				self.pool.get('hr.employee').create(cr,uid,value)				
			cr_odoo1.close()
			if conn_odoo1 is not None:
				conn_odoo1.close()
			return True