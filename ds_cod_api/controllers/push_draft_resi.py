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


# class cod_api(http.Controller):

# 	@http.route(['/create/resi',], type='json',method="POST", auth="user")
# 	def create_resi(self,**post):
		
# 		print "resi===============",request.session_id,request.cr,request.uid
# 		x = request.registry['account.invoice'].search(request.cr,request.uid,[])
# 		print "====================",x

# 		return {"status": "OK"}