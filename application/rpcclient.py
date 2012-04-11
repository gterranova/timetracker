#!/usr/bin/python
# -*- coding: utf-8 -*-

import urllib
import simplejson as json
import collections
Result = collections.namedtuple('Result', 'id,result,error')

SEARCH_BASE = 'http://www.terranovanet.it/cgi-bin/ttweb/ttweb.py'

class rpcClient(object):
    def __init__(self, proxy=None):
        self.id = 0        
        self.proxy = proxy or SEARCH_BASE

    def _rpc(self, method, **kwargs):
        kwargs.update({'method': method, 'output': 'json'})
        url = SEARCH_BASE + '?' + urllib.urlencode(kwargs)
        print "RPC: Method: %s Params: %s" % (method, kwargs)
        result = json.load(urllib.urlopen(url))
        result = dict([(str(k), v) for k, v in result.items()])
        print "RPC: Result:", result
        
        if result['error']:
            print "ERROR"
        # namedtuple doesn't work with unicode keys.
        return Result(id=result['id'], result=result['result'],
                      error=result['error'], )

    def __getattr__(self, method):
        if not self.__dict__.has_key(method):
            def func(**kwargs):
                return self._rpc(method, **kwargs)
            return func
        return self.__dict__[attrName]            

