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
		pt_pool = request.registry['acc.invoice.line.pt']
		invl_pool = request.registry['account.invoice.line']
		invlt_pool = request.registry['account.invoice.line.tracking']
		analytic_pool = request.registry['account.analytic.account']
		response = {}
		alldir=dir(request.httprequest)

		pod_data = request.jsonrequest.get('pod_data',{})

		status = 'ERROR'
		nik = pod_data.get('nik',False)

		resi_number = pod_data.get('resi_number',False)
		resi_status = pod_data.get('resi_status',False)
		pod_datetime = pod_data.get('trackingDtm',False)
		cod_value = pod_data.get('amount',0.0)
		kode_cabang = pod_data.get('kodeCabang',False)
		username = pod_data.get('username',False)
		payment_type = pod_data.get('payment_type','CASH')


		write_value = {}
		invl_id=False
		if resi_number and resi_status:
			invl_id = invl_pool.search(request.cr,request.uid,[('name','=',resi_number)],context={})
		message = ''
		emp_id=False
		analytic_id = False
		if nik and nik!="":
			emp_id = gesit_pool.search(request.cr,request.uid,[('nik','=',nik)],context={})
			if not emp_id:
				message+='Karyawan %s tidak ditemukan'%nik
				status = 'ERROR'
				response.update({
					'status': status,
					'message':message,
					})
		if kode_cabang and kode_cabang!="":
			analytic_id = analytic_pool.search(request.cr,request.uid,[('code','=',kode_cabang)])
			if not analytic_id:
				message+=',Cabang %s tidak ditemukan'%kode_cabang
				status = 'ERROR'
				response.update({
					'status': status,
					'message':message,
					})
		pt_id=False
		if payment_type and payment_type!="":
			pt_id = pt_pool.search(request.cr,request.uid,[('code','=',payment_type)],context={})
			if pt_id:
				pt_id=pt_id[0]
			
		if resi_number and not invl_id:
			if not invl_id:
				message+=(status=='ERROR' and ',' or '')+'Resi %s tidak ditemukan'%resi_number
				status = 'ERROR'
				response.update({
					'status': status,
					'message':message,
					})
		else:
			if emp_id:
				write_value.update({'sigesit':emp_id[0]}) 
			if analytic_id:
				write_value.update({'analytic_destination':analytic_id and analytic_id[0] or False,})
			if resi_status:
				write_value.update({'internal_status':resi_status})
			if pod_datetime:
				write_value.update({'pod_datetime':pod_datetime})
			if payment_type and payment_type!="":
				write_value.update({'payment_type':pt_id})
			if cod_value and cod_value>0.0:
				write_value.update({'price_cod':cod_value})
			# if resi_status=='DLV':
			# 	write_value.update({'price_cod':cod_value,'internal_status':'sigesit','payment_type':pt_id,'pod_datetime':pod_datetime})
			# elif resi_status=='LOST':
			# 	write_value.update({'internal_status':'lost','pod_datetime':pod_datetime})
			# elif resi_status=='ANT':
			# 	write_value.update({'internal_status':'antar','pod_datetime':pod_datetime}) #status dalam pengantaran
			# elif resi_status=='RTA':
			# 	write_value.update({'internal_status':'rta','sigesit':False,'pod_datetime':pod_datetime}) #status return to a
			# elif resi_status=='RTG':
			# 	write_value.update({'internal_status':'rtg','sigesit':False,'pod_datetime':pod_datetime}) #status return to gerai
			# elif resi_status=='RTS':
			# 	write_value.update({'internal_status':'rts','sigesit':False,'pod_datetime':pod_datetime}) #status return to shipper
			# else:
			# 	write_value.update({'internal_status':'open','sigesit':False,'pod_datetime':pod_datetime})

			result = invl_pool.write(request.cr,request.uid,invl_id,write_value,context={})
			invline = invl_pool.browse(request.cr,request.uid,invl_id[0])
			max_invl_id_track_sequence = 0
			if invline.tracking_ids:
				max_invl_id_track_sequence = max([x.sequence for x in invline.tracking_ids])

			tracking_value = {
				"invoice_line_id": invline.id,
				"sequence": max_invl_id_track_sequence+1 ,
				"resi_number": resi_number,
				"pod_datetime": pod_datetime,
				"position_id": analytic_id and analytic_id[0] or False,
				"status": resi_status,
				"user_tracking": username,
				"sigesit": emp_id and emp_id[0] or False,
				}
			invlt_pool.create(request.cr,request.uid,tracking_value)
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