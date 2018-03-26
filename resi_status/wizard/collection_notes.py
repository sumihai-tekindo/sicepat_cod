from openerp import models, fields,api, _
from datetime import datetime
from openerp.osv import osv, expression
from openerp.report import report_sxw


class account_invoice_line_collection(models.Model):
	_name = "account.invoice.line.collection"

	notes = fields.Text("Notes")

	def default_get(self, cr, uid, fields, context=None):
		res = super(account_invoice_line_collection,self).default_get(cr,uid,fields,context=context)
		journal_id=False
		if context and context.get('active_ids',False):
			invoice_lines = self.pool.get('account.invoice.line').browse(cr,uid,context.get('active_ids',False))
			rml_parser = report_sxw.rml_parse(cr, uid, 'reconciliation_widget_aml', context=context)
			notes = "Dear Admin Cabang %s, \n"%(invoice_lines[0].analytic_destination and invoice_lines[0].analytic_destination.name or "")
			notes += "tolong followup resi cod dengan detail sebagai berikut: \n\n"
			n=1
			summary = 0.0
			maxlen=0
			for x in invoice_lines:
				note="%s	%s	%s	%s\n"%(n,x.name,x.stt_date,rml_parser.formatLang(x.price_subtotal, currency_obj=x.invoice_id.currency_id))
				notes+=note
				if len(note)>=maxlen:
					maxlen=len(note)
				n+=1
				summary+=x.price_subtotal
			print "----",maxlen
			notes+=maxlen*"_"+"________\n"
			notes+="Total %s\n"%(rml_parser.formatLang(summary, currency_obj=x.invoice_id.currency_id))
			notes+=maxlen*"_"+"________\n"
			notes+="\nPembayaran COD dapat melalui :\n\
Bank BCA\n\
No Rek : 270 393 5656\n\
Atas Nama : SiCepat Ekspres Indonesia\n"
		res.update({
			'notes':notes,
			})

		return res
