from openerp import models, fields
from datetime import datetime
import psycopg2
import psycopg2.extras

from openerp.osv import expression

class account_analytic_account(models.Model):
	_inherit = "account.analytic.account"

	odoo1_id = fields.Integer("Odoo1 Database ID")
	rds_id = fields.Integer("RDS ID")
	active = fields.Boolean("Active")
	tag = fields.Selection([('head_office',"Head Office"),
			('region','Region'),
			('provinsi',"Provinsi"),
			('kota',"Kabupaten/Kota"),
			('gerai',"Gerai"),
			('toko','Toko'),
			('cabang','Cabang'),
			('transit','Transit'),
			('agen','Agen'),
			('pusat_transitan','Pusat Transitan'),
			('perwakilan',"Perwakilan"),
			('other',"Lainnya")],"Category")

	def fetch_analytic(self,cr,uid,context=None):
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
			query_sel="""select aa.* ,aap.code as parent_code
						from account_analytic_account aa
						left join account_analytic_account aap on aa.parent_id=aap.id 
						where aa.tag in ('provinsi','region','kota','cabang','transit','gerai','perwakilan','agen')"""
			cr_odoo1.execute(query_sel)
			records = cr_odoo1.fetchall()

			local_ids = self.pool.get('account.analytic.account').search(cr,uid,[('tag','in',('provinsi','region','kota','cabang','transit','gerai','perwakilan','agen'))])
			local_analytic = {}
			if local_ids and local_ids!=[]:
				local = self.pool.get('account.analytic.account').browse(cr,uid,local_ids)
				for x in local:
					local_analytic.update({x.code:x.id})
			exists = []
			not_exists = []
			for row in records:
				d_row = dict(row)
				if d_row.get('code',False) in local_analytic.keys():
					exists.append(d_row)
				else:
					not_exists.append(d_row)
			for e in exists:
				value = {
					'name': e.get('name',False),
					'tag' : e.get('tag',False),
					'type': len(e.get('code',''))> 4 and 'normal' or 'view',
					'active': e.get('active',True),
					'rds_id': e.get('rds_id',False),
					'code': e.get('code',False),
					'parent_id': local_analytic.get(e.get('parent_code',False),False),
					'odoo1_id': e.get('id',False)
					}
				# print "==========write==========",value,local_analytic.get(e.get('code',False))
				self.pool.get('account.analytic.account').write(cr,uid,local_analytic.get(e.get('code',False)),value)

			for ne in not_exists:
				value = {
					'name': ne.get('name',False),
					'tag' : ne.get('tag',False),
					'type': len(ne.get('code',''))> 4 and 'normal' or 'view',
					'code': ne.get('code',False),
					'active': ne.get('active',True),
					'rds_id': ne.get('rds_id',False),
					'parent_id': local_analytic.get(ne.get('parent_code',False),False),
					'odoo1_id': ne.get('id',False)
					}
				# print "=========create===========",value
				self.pool.get('account.analytic.account').create(cr,uid,value)				
			cr_odoo1.close()
			if conn_odoo1 is not None:
				conn_odoo1.close()
			return True