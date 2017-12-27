#!/usr/bin/python
# -*- coding: utf-8 -*-
#/#############################################################################
#
#   Copyright (C) 2016 Pambudi Satria (<https://github.com/pambudisatria>). 
#   All Rights Reserved
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
#/#############################################################################

{
    'name': "Indonesia Bank",

    'summary': """
        Indonesia Bank Identifier Code""",

    'description': """
    """,

    'author': "Pambudi Satria",
    'website': "https://github.com/pambudisatria",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Localization/Indonesia',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'data/res.bank.csv',
    ],
    # only loaded in demonstration mode
    'demo': [],
    'qweb': [],
    'installable': True,
    'auto_install': True,
}