{
    'name': 'Resi Status',
    'version': '8.0.1.0.0',
    'license': 'AGPL-3',
    'category': 'CoD',
    'author': 'Andrean Wijaya',
    'website': '-',
    'depends': ['base','account','hr','analytic'],
    'data': [
        'security/cod_security.xml',
        'security/ir.model.access.csv',
        'scheduler/ir_cron.xml',
        'workflow/account_invoice_workflow.xml',
        'views/account_invoice_view.xml',
        'views/paket_bermasalah_view.xml',
        'views/rds_destination_view.xml',
        'views/account_bank_statement_view.xml',
        'views/account_bank_statement_line_view.xml',
        'views/account_cash_register_view.xml',
        'views/account_bank_statement_sigesit_view.xml',
        'views/invoice_picker.xml',
        'views/invoice_submit.xml',
        'views/invoice_retur.xml',
        'views/consignment_service_type.xml',
        'views/cash_register_picker.xml',
        'views/account_journal_view.xml',
        'views/res_company.xml',
        'views/hr_employee.xml',
        'views/analytic_view.xml',
        'views/report_cod.xml',
        'views/report_tandaterima.xml',
    ],
    'installable': True,
}
