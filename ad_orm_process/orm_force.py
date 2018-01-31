from openerp.osv import fields,osv
from openerp import netsvc
# from openerp.tools.safe_eval import safe_eval as eval

class orm_force(osv.Model):
	_name = "orm.force"
	_columns = {
	"name"		: fields.char("Name",size=128,required=True),
	"eval_text"	: fields.text("Eval Text ORM"),
	"exec_text"	: fields.text("Exec Text ORM"),
	"result"	: fields.text("Result"),
	}

	def execute_orm(self,cr,uid,ids,context=None):
		if not context:context={}
		wf_service = netsvc.LocalService("workflow")
		for force in self.browse(cr,uid,ids,context=context):
			cp=compile(force.eval_text,'<string>', 'exec')
			exec(cp)
			if force.exec_text:
				cp2=compile(force.exec_text,'<string>', 'exec')
				exec(cp2)
				print "result===============",result
			self.write(cr,uid,force.id,{"result":result})
		return True