from openerp import models, fields, api, _
from datetime import datetime, timedelta
import requests
from openerp.osv import osv, expression

class ConsignmentServiceType(models.Model):
    _name = "consignment.service.type"
    _inherit = ['mail.thread']
    _description = 'Consignment Service Type'
    _order = 'code, name asc'

    name = fields.Char('Service Name', required=True, track_visibility='onchange')
    code = fields.Char('Code', required=True, select=True, track_visibility='onchange', copy=False)
    active = fields.Boolean(default=True, track_visibility='onchange')
    

    _sql_constraints = [
            ('code_unique', 'UNIQUE(code)', 'Code must be unique'),
        ]

    @api.returns('self', lambda value: value.id)
    @api.multi
    def copy(self, defaults=None):
        if not defaults:
            defaults = {}
        defaults.update({
            'name': _("%s (copy)") % self.name,
            'code': _("%s (copy)") % self.code,
        })
        return super(ConsignmentServiceType, self).copy(defaults)

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            name_get = rec.name
            if self._context.get('show_code'):
                name_get = rec.code
            result.append((rec.id, "%s" % (name_get)))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', '=', name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()