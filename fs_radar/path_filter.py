#!/usr/bin/env python
# *-* encoding: utf-8 *-*

import re


def ruleToRegexp(rule):
    """Given a glob-like path (the `rule`) it returns a regular expression
    to match it"""

    is_dir = rule.endswith('/')
    if is_dir:
        rule = rule[:-1]

    any_depth = not rule.startswith('./')

    # remove any occurrence of ./ (but not ../) from the rule
    # (we're interested in the first(s) occurrence(s) )
    rule = re.sub('([^.]|^)(\\./)+', '\\1', rule)

    if rule == '.':
        return '.*'

    return ('(.*/)?' if any_depth else '^(\\./)?') + \
        re.escape(
             # substitute multiple asterisks with a single *
             re.sub('\*+', '*', rule)
        ).replace('\\*', '.*?') + \
        ('(/|$)' if is_dir else '$')


def makePathFilter(rules):
    """Accept a list of `rules` and return a function that, given a path,
    return True if the path has to be accepted or False otherwise"""

    includeRegExps = []
    excludeRegExps = []
    doNotExcludeRegExps = []

    for rule in rules:
        if rule.startswith('+'):
            rule = rule[1:]
            reg = ruleToRegexp(rule)
            doNotExcludeRegExps.append(reg)
        elif rule.startswith('!'):
            rule = rule[1:]
            reg = ruleToRegexp(rule)
            excludeRegExps.append(reg)
        else:
            reg = ruleToRegexp(rule)
            includeRegExps.append(reg)

    INCLUDE_REGEXP = re.compile('|'.join(includeRegExps)) if includeRegExps else None
    EXCLUDE_REGEXP = re.compile('|'.join(excludeRegExps)) if excludeRegExps else None
    DO_NOT_EXCLUDE_REGEXP = re.compile('|'.join(doNotExcludeRegExps)) if doNotExcludeRegExps else None

    def path_filter(path):
        return bool(path and  # noqa
            (INCLUDE_REGEXP and INCLUDE_REGEXP.match(path)) and
            ((not (EXCLUDE_REGEXP and EXCLUDE_REGEXP.match(path))) or
             (DO_NOT_EXCLUDE_REGEXP and DO_NOT_EXCLUDE_REGEXP.match(path))
            )
        )

    return path_filter


def makeDirFilter(rules):
    '''Transform file rules to dir rules.

    That means that for every rule that was matching a file now match
    his parent directory instead.
    '''

    dir_rules = []

    for rule in rules:
        if rule.endswith('/'):
            dir_rules.append(rule)
        elif rule.startswith('!'):
            dir_rules.append(rule)
        elif rule:
            parts = (rule.startswith('+') and rule[1:] or rule).rsplit('/', 1)
            if rule == '.' or len(parts) == 1:
                dir_rules.append('*')
            else:
                dir_rules.append(rule.rsplit('/', 1)[0] + '/')

    return makePathFilter(dir_rules)
