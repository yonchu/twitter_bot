#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import json

__all__ = ['pp', 'pp_str']


class MyEncoder (json.JSONEncoder):
    def default(self, o):
        try:
            iterable = iter(o)
        except TypeError:
            pass
        else:
            return list(iterable)

        try:
            return json.JSONEncoder.default(self, o)
        except TypeError:
            return str(o)


def pp(obj):
    print(pp_str(obj))


def pp_str(obj):
    orig = json.dumps(obj,
                      indent=4,
                      sort_keys=True,
                      skipkeys=True,
                      cls=MyEncoder)
    return eval("u'''%s'''" % orig).encode('utf-8')
