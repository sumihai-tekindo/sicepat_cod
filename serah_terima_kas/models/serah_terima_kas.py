from openerp import models, fields, api

class serah_terima_kas(models.TransientModel):

    _name = "serah.terima.kas"

    serah_terima_ids = fields.Many2many("account.bank.statement","account_bank_statement_rel","statement_id","bank_statement_id","Journal Items")

    @api.model
    def default_get(self,fields):
        res = super(serah_terima_kas,self).default_get(fields)
        serah_terima_ids = self.env.context.get('active_ids',False)
        if serah_terima_ids:
            
            res.update({
                'serah_terima_ids': serah_terima_ids,
            })
        return res

    @api.multi
    def generate_serah_terima_kas(self):
        if self.env.context is None:
            self.env.context = {}
        proxy = self.env['account.bank.statement'].search([('journal_id.type','=','cash')])

        serah_terima_id = self.env['serah.terima.kas'].browse(serah_terima_ids)

        
        # belum selesai

