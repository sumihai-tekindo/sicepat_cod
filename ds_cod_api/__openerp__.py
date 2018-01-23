{
    'name': 'COD API',
    'version': '8.0.1.0.0',
    'license': 'AGPL-3',
    'category': 'CoD',
    "summary":"""
        * login through jsonrpc post to url host/web/session/authenticate
          pass these parameters:
          {
                "jsonrpc": "2.0",
                "method": "login",
                "params": {"db":"db_name","login":"username","password":"password"}

          }
        * to create resi:
          post json data to url host/resi/update using these parameters:
          headers 
          {
          "session_id":"session token that have been received from login",
          "Content-Type":"application/json",
          }
          body
          {
                "jsonrpc": "2.0",
                "method": "update_resi",
                "params": {"resi_number":"000084119456","nik":"16110081","resi_status":"DLV"}
          }

    """,
    'author': 'Dedi Sinaga',
    'website': '-',
    'depends': ['base','account','hr','resi_status'],
    'data': [

    ],
    'installable': True,
}
