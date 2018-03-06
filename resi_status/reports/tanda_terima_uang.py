from openerp.osv import osv
from openerp.report import report_sxw


class tanda_terima_uang(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(tanda_terima_uang, self).__init__(cr, uid, name, context)
        self.localcontext.update({

        })


class wrapped_report_tanda_terima_uang(osv.AbstractModel):
    _name = 'report.resi_status.tanda_terima'
    _inherit = 'report.abstract_report'
    _template = 'resi_status.tanda_terima'
    _wrapped_report_class = tanda_terima_uang