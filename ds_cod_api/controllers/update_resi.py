# -*- coding: utf-8 -*-
import logging
import werkzeug
import json

from openerp import SUPERUSER_ID
from openerp import http

from openerp import tools
from openerp.http import request
from openerp.tools.translate import _
from openerp.addons.website.models.website import slug
from openerp.addons.web.controllers.main import login_redirect
import simplejson
from openerp.addons.web.controllers.main import Session

class Sessionx(Session):
	
	@http.route('/web/session/authenticate', type='json', auth="none")
	def authenticate(self, db=None, login=None, password=None, base_location=None):
		pod_data = request.jsonrequest.get('pod_data',{})
		if not db:
			db=pod_data.get('db',False)
		if not login:
			login=pod_data.get('login',False)
		if not password:
			password=pod_data.get('password',False)
		res=super(Sessionx,self).authenticate(db,login,password,base_location=base_location)

		return self.session_info()

class update_resi(http.Controller):
	@http.route(['/resi/update',], type='json',method="POST", auth="user")
	def update_resi(self,**post):
		gesit_pool = request.registry['hr.employee']
		invl_pool = request.registry['account.invoice.line']
		response = {}
		alldir=dir(request.httprequest)


		pod_data = request.jsonrequest.get('pod_data',{})

		status = 'ERROR'
		nik = pod_data.get('nik',False)

		resi_number = pod_data.get('resi_number',False)
		resi_status = pod_data.get('resi_status',False)
		pod_datetime = pod_data.get('pod_datetime',False)
		cod_value = pod_data.get('cod_value',0.0)
		invl_id=False
		if resi_number and resi_status:
			invl_id = invl_pool.search(request.cr,request.uid,[('name','=',resi_number)],context={})
		message = ''
		if nik :
			emp_id = gesit_pool.search(request.cr,request.uid,[('nik','=',nik)],context={})
			if not emp_id:
				message+='Karyawan %s tidak ditemukan'%nik
				status = 'ERROR'
				response.update({
					'status': status,
					'message':message,
					})
		if not invl_id:
			if not invl_id:
				message+=(status=='ERROR' and ',' or '')+'Resi %s tidak ditemukan'%resi_number
				status = 'ERROR'
				response.update({
					'status': status,
					'message':message,
					})
		else:
			if emp_id:
				write_value = {'sigesit':emp_id[0]}
			else:
				write_value = {}
			if resi_status=='DLV':
				write_value.update({'price_cod':cod_value,'internal_status':'sigesit'})
			elif resi_status=='LOST':
				write_value.update({'internal_status':'lost'})
			elif resi_status=='ANT':
				write_value.update({'internal_status':'antar'}) #status dalam pengantaran
			elif resi_status=='RTA':
				write_value.update({'internal_status':'rta','sigesit':False}) #status return to a
			elif resi_status=='RTG':
				write_value.update({'internal_status':'rtg','sigesit':False}) #status return to gerai
			elif resi_status=='RTS':
				write_value.update({'internal_status':'rts','sigesit':False}) #status return to shipper
			else:
				write_value.update({'internal_status':'open','sigesit':False})
			result = invl_pool.write(request.cr,request.uid,invl_id,write_value,context={})
			if result:
				response = {
					'status':'OK',
					'message': 'Data Entry Valid'
					}
			else:
				response = {
					'status':'ERROR',
					'message': 'An Odoo Internal Server is occured. Please contact the administrator!'
					}
		return response