# -*- coding: utf-8 -*-
import logging
import werkzeug
import json
import base64
from openerp import SUPERUSER_ID
from openerp import http

from openerp import tools
from openerp.http import request
from openerp.tools.translate import _
from openerp.addons.web.controllers.main import content_disposition
import simplejson


class custom_reports_downloader(http.Controller):
	#/web/custom_report?model=account.invoice&func=supplier_invoice_xls_data&ids=%s'%ids,
	@http.route('/web/custom_report', type='http', auth="user")
	# @serialize_exception
	def custom_report(self,model,method,data_ids):
		Model = request.registry[model]
		cr, uid, context = request.cr, request.uid, request.context
		try:
			ids=eval(data_ids)
		except:
			ids=data_ids
		filecontent,content_type,filename = getattr(Model,method)(cr,uid,ids,context=context)
		# print "==========",filecontent
		#filecontent = base64.b64decode( file_datas or '')
		if filename and filecontent:
			return request.make_response(filecontent,
						[('Content-Type', content_type),
						 ('Content-Disposition', content_disposition(filename))]) 
		return request.not_found()