from openerp import models, fields
from datetime import datetime
import requests
import json
from openerp.osv import expression

class rds_destination(models.Model):
	_inherit = "rds.destination"

	def fetch_rds_destination(self,cr,uid,context=None):
		url = "http://api.sicepat.com/customer/destination"
		api_key = "2f9028dcb1ad9a58fc22e8948524a5c2"
		res = {}

		values={"api-key":api_key}
		fetch=requests.get(url,params=values)
		res=json.loads(fetch.text)
		existing_dest_ids = self.search(cr,uid,[])
		existing_dests = self.browse(cr,uid,existing_dest_ids)
		existing_dest = {}

		for d in existing_dests:
			existing_dest.update({d.code:d.id})
		# print "==========================",existing_dest
		for x in res['sicepat']['results']:
			values = {
				'name': x.get('subdistrict',False),
				'province': x.get('province',False),
				'city': x.get('city',False),
				'subdistrict': x.get('subdistrict',False),
				'code': x.get('destination_code',False),
			}

			# print "##################",x.get('destination_code',False) in existing_dest.keys()
			
			if x.get('destination_code',False) in existing_dest.keys():
				self.pool.get('rds.destination').write(cr,uid,existing_dest.get(x.get('subdistrict',False),False),values)
			else:
				self.pool.get('rds.destination').create(cr,uid,values)
		return True