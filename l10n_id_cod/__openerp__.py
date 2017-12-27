# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2016 Sicepat Ekspres (<http://www.sicepat.com>).
#    @author Pambudi Satria <pambudi.satria@yahoo.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': "Sicepat Ekspres COD - Chart of accounts",

    'summary': """Chart of Account for CoD process in PT Sicepat Ekspres Indonesia""",

    'description': """
    """,

    'author': "Dedi Sinaga",
    'website': "http://www.sicepat.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Localization/Account Charts',
    'version': '8.0.0.1.0',

    # any module necessary for this one to work correctly
    'depends': [
        'account_asset',
        'analytic',
        'account',
        'l10n_id_bank',
    ],

    # always loaded
    'data': [
        'datas/res_company.xml',
        'datas/account_type.xml',

        'datas/account_chart_template.xml',
        'datas/account.account.template.csv',
        # 'datas/account_tax_template.xml',
        'datas/account_chart_template_after.xml',
        'datas/l10n_id_SCE_wizard.yml',
        'datas/account_journal.xml',
        'datas/res_partner_bank.xml',
    ],

    # only loaded in demonstration mode
    'demo': [
    ],

    'qweb': [],
    'installable': True,
    'auto_install': False,
}