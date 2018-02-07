

class account_invoice(models.Model):
	_inherit = "account.invoice"

	def scheduled_stt_pull(self,cr,uid,context=None):
		
		
		cnx = mysql.connector.connect(**config)
		cur = cnx.cursor()
		querystt = """select tgltransaksi,pengirim,nostt,penerima,codNilai 
					from rudydarw_sicepat.stt 
					where codNilai>0.0 and iscodpulled != 1 
					order by tgltransaksi asc,pengirim asc,nostt asc
				 """
		
		cur.execute(querystt)
		result = cur.fetchall()
		

		############################################################################################
		# group the data to make it easier creating invoice
		# {tgl_transaksi:{pengirim:{'00000123123':{'penerima':'nama penerima','price_unit':50000}}}}
		############################################################################################
		data = {}
		all_cod_cust = []
		for r in result:
			
			data_tgl = data.get(r[0],{})
			tgl_pengirim = data_tgl.get(r[1],{})
			all_cod_cust.append(r[1])
			tgl_pengirim.update({r[2]:{'penerima':r[3],'price_unit':r[4]}})
			data_tgl.update({r[1]:tgl_pengirim})
			data.update({r[0]:data_tgl})
		all_cod_cust=list(set(all_cod_cust))

		partner_cod_ids = self.pool.get('res.partner').search(cr,uid,[('name','in',all_cod_cust)])
				# print "----------",nomo
		partner_cod = {}
		if all_cod_cust and partner_cod_ids and (len(all_cod_cust)!=len(partner_cod_ids)):
			for pc in self.pool.get('res.partner').browse(cr,uid,partner_cod_ids):
				partner_cod.update({pc.name:pc.id})
		not_in_partner = []
		for x in all_cod_cust:
			if not partner_cod.get(x,False):
				not_in_partner.append(x)

		for nip in not_in_partner:
			print "-----------------",nip
			if nip and nip!=None and nip !="":
				pt_id = self.pool.get('res.partner').create(cr,uid,{'name':nip,'customer':True,'supplier':True})
				partner_cod.update({nip:pt_id})

		user = self.pool.get('res.users').browse(cr,uid,uid,context=context)
		partner = user.company_id.cod_customer
		domain = [('type', '=', 'sale'),
			('company_id', '=', user.company_id.id)]
		journal_id = self.pool.get('account.journal').search(cr,uid,domain, limit=1)
		created_invoices = []
		for tgl in data:
			if tgl:
				sender = data.get(tgl,{})
				for pengirim in sender:
					if pengirim:
						values = {
							'partner_id'	:	partner.id,
							'date_invoice'	:	tgl.strftime('%Y-%m-%d'),
							'journal_id'	:	journal_id and journal_id[0],
							'invoice_type'	:	'out_invoice',
							'account_id'	:	partner.property_account_receivable.id,
							'state'			:	'draft',
							'sales_person'	:	uid,
							'invoice_line'	:	[],
							'cod_customer'	: 	partner_cod.get(pengirim,False),
						}
						invoice_line = []
						awbs = sender.get(pengirim,{})
						for awb in awbs:
							lines = {
								'name'				:	awb,
								'account_id'		:	user.company_id.account_temp_1.id,
								'price_unit'		:	awbs.get(awb).get('price_unit',0.0),
								'recipient'			:	awbs.get(awb).get('recipient',0.0),
								'price_package'		:	awbs.get(awb).get('price_unit',0.0),
								'internal_status'	:	'open',
							}
							invoice_line.append((0,0,lines))
					values.update({'invoice_line':invoice_line})
					# print "============",values
					inv_id = self.pool.get('account.invoice').create(cr,uid,values)
					if inv_id:
						created_invoices.append(inv_id)
		invoice_line = self.pool.get('account.invoice.line').search(cr,uid,[('invoice_id','in',created_invoices)])
		
		cnx.close()
		cur.close()
		to_update = ""
		for x in self.pool.get('account.invoice.line').browse(cr,uid,invoice_line):
			to_update+="'"+x.name+"',"
		if to_update!="":
			to_update=to_update[:-1]
			query_update = """update stt set iscodpulled=1 where nostt in (%s)"""%to_update
			cnx2 = mysql.connector.connect(**config)
			cur2 = cnx2.cursor()
			cur2.execute(query_update)
			cur2.close()
			cnx2.close()
		return result
