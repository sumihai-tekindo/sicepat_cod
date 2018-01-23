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


class update_resi(http.Controller):

	@http.route(['/resi/update',], type='json',method="POST", auth="user")
	def update_resi(self,**post):
		gesit_pool = request.registry['hr.employee']
		invl_pool = request.registry['account.invoice.line']
		response = {}
		nik = post.get('nik',False)
		resi_number = post.get('resi_number',False)
		resi_status = post.get('resi_status',False)
		if resi_number and nik and resi_status:
			emp_id = gesit_pool.search(request.cr,request.uid,[('nik','=',nik)],context={})
			print "resi===============",emp_id
			invl_id = invl_pool.search(request.cr,request.uid,[('name','=',resi_number)],context={})
			message = ''
			if not emp_id or not invl_id:
				if not emp_id:
					message+='Karyawan dengan NIK %s tidak ditemukan'%nik
					status = 'ERROR'
				if emp_id and not invl_id:
					message+='Resi %s tidak ditemukan'%resi
					status = 'ERROR'
				if not emp_id and not invl_id:
					message+=', dan Resi %s tidak ditemukan'%resi
					status = 'ERROR'
				response.update({
					'status': status,
					'message':message,
					})
			else:
				write_value = {'sigesit':emp_id[0]}
				if resi_status=='DLV':
					write_value.update({'internal_status':'sigesit'})
				if resi_status=='LOSS':
					write_value.update({'internal_status':'lost'})
				print "###################",request.cr,request.uid,write_value
				result = invl_pool.write(request.cr,request.uid,invl_id,write_value,context={})
				if result:
					response = {
						'status':'OK',
						'message': 'Data Entry Valid'
						}
		return response