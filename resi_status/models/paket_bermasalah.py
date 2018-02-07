from openerp import models, fields

class paket_bermasalah(models.Model):
    _name = 'paket.bermasalah'

    no_resi = fields.Many2one('account.invoice.line', string='No. Resi',required=True)
    kondisi = fields.Selection([
    	('lost','Hilang'),
    	('retur','Retur'),
    	], string='Kondisi')
    no_tiket = fields.Char(string="No. Tiket")
    note = fields.Char(string="Keterangan")
    status = fields.Selection([('draft',"Draft"),('closed',"Closed")])