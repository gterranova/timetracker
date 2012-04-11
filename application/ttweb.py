#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys, os
import cgi as cgimodule
import cgitb
cgitb.enable()

import urllib

curdir = os.path.join(os.path.dirname(__file__))
site_packages = os.path.join(curdir,'..', 'site_packages')
if site_packages not in sys.path:
    sys.path.insert(0, site_packages)
if curdir not in sys.path:
    sys.path.insert(0, curdir)

import datetime
import simplejson as json
##from database import Activity, ActivityLog, session
import functions as server

def defaultScreen(**kwargs):
    print "Content-type: text/plain\n"
    print "Default Screen"

def parse_get_qs(qs, fs, keep_blank_values=0, strict_parsing=0):
    r = {}
    for name_value in qs.split('&'):
        nv = name_value.split('=', 2)
        if len(nv) != 2:
            if strict_parsing:
                raise ValueError, "bad query field: %r" % (name_value,)
            continue
        name = urllib.unquote(nv[0].replace('+', ' '))
        value = urllib.unquote(nv[1].replace('+', ' '))
        if len(value) or keep_blank_values:
            if r.has_key(name):
                r[name].append(value)
            else:
                r[name] = [value]

    # Only append values that aren't already in the FieldStorage's keys;
    # This makes POSTed vars override vars on the query string
    for key, values in r.items():
        if not fs.has_key(key):
            for value in values:
                fs.list.append(cgimodule.MiniFieldStorage(key, value))
    return fs
    
if __name__ == "__main__":
    params = cgimodule.FieldStorage(keep_blank_values=1)
    params = parse_get_qs(os.environ['QUERY_STRING'], params)
        
    kwargs = {}    
    for p in params:
        try:
            kwargs[p] = params[p].value
        except:
            kwargs[p] = [l.value for l in params[p]]

    action = kwargs.pop('method', None)
    output = kwargs.get('output', 'json')

    if action and hasattr(server, action):
        f = getattr(server, action)
        if output=='json':
            print "Content-type: application/json\n"
            print json.dumps(f(**kwargs))
        else:
            print "Content-type: text/plain\n"
            print f(**kwargs)
    else:
        defaultScreen(**kwargs)
        
