import os, sys
from distutils.core import setup
import py2exe

sys.path.insert(0, os.path.join(os.path.dirname(__file__),"application"))

setup(windows=[
    {"script": 'timetracker.pyw',
    "icon_resources": [(1, "timetracker.ico")]
    }],
    options={"py2exe" : {
    "packages": ["sqlalchemy"]
    }}
) 
