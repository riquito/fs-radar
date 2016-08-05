import logging

BASE = {
    'format': '%(message)s',
    'level': logging.INFO
}

VERBOSE = {**BASE, **{
    'format': '%(levelname)s:%(name)s:%(message)s',
    'level': logging.DEBUG
}}

QUIET = {**BASE, **{
    'level': logging.WARN
}}
