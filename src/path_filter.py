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

    return ('(.*/)?' if any_depth else '^') + \
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

    INCLUDE_REGEXP = re.compile('|'.join(includeRegExps))
    EXCLUDE_REGEXP = re.compile('|'.join(excludeRegExps))
    DO_NOT_EXCLUDE_REGEXP = re.compile('|'.join(doNotExcludeRegExps)) if doNotExcludeRegExps else None

    def path_filter(path):
        return bool(
            INCLUDE_REGEXP.match(path) and
            (not EXCLUDE_REGEXP.match(path) or (DO_NOT_EXCLUDE_REGEXP and DO_NOT_EXCLUDE_REGEXP.match(path)))
        )

    return path_filter


if __name__ == '__main__':
    rules = [
        "*.js",
        ".jsx",
        "a/dir/",
        "a/glob/**/file.png",
        "./only-at-root",
        "app/cache/*",
        "!app/cache/*.txt",
        "+app/cache/do-not-exclude-me.txt"
    ]

    path_filter = makePathFilter(rules)

    assert path_filter('root-file.js')
    assert path_filter('any/depth/file.js')
    assert path_filter('.jsx')
    assert path_filter('any/depth/.jsx')
    assert path_filter('bar.jsx') is False
    assert path_filter('only-at-root')
    assert path_filter('any/depth/only-at-root') is False
    assert path_filter('') is False
    assert path_filter('a/dir/')
    assert path_filter('a/dir/file')
    assert path_filter('a/dir')
    assert path_filter('a/dirfoo') is False
    assert path_filter('a/glob/one-level/file.png')
    assert path_filter('a/glob/one-level/nofile.png') is False
    assert path_filter('a/glob/multi/level/file.png')
    assert path_filter('app/cache/include-me')
    assert path_filter('app/cache/exclude.txt') is False
    assert path_filter('app/cache/do-not-exclude-me.txt')

    print('All tests passed')
