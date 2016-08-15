#!/usr/bin/env python
# *-* encoding: utf-8 *-*

import logging
import toml

logger = logging.getLogger(__name__)


class ConfigException(Exception):
    pass


def load_from_toml(settings_path):
    with open(settings_path) as fp:
        text = fp.read()
        try:
            data = toml.loads(text)
        except Exception as e:  # is unnamed :-/
            message = 'Error while reading toml file: {}'.format(e)
            raise ConfigException(message) from e

    for key in ('fs_radar', 'group'):
        if key not in data:
            raise ConfigException('Config file requires a namespace named \'%s\'' % key)

    try:
        data['fs_radar']['basedir']
    except KeyError as e:
        raise ConfigException('Config file requires a field \'basedir\' in the namespace \'fs_radar\'') from None

    for group in data['group']:
        cmd_confs = data['group'][group]

        try:
            cmd_confs['cmd']
        except KeyError:
            raise ConfigException('Config file requires a field \'cmd\' in every namespace') from None

        try:
            cmd_confs['rules'] = _normalize_rules(cmd_confs['rules'])
        except KeyError:
            raise ConfigException('Config file requires a field \'rules\' in every namespace') from None

    return data


def _normalize_rules(rules):
    '''Ensure that rules are in list format

    `rules` can be either a list (in such case is returned as is)
    or a string.
    The string format is:
    - lines starting with # are skipped
    - empty (trimmed) lines are skypped
    - all other lines are threated as a glob path
    '''
    if isinstance(rules, str):
        return list(_parse_rules_string(rules))
    else:
        return rules


def _parse_rules_string(rules_string):
    for rule in rules_string.split('\n'):
        stripped_rule = rule.strip()
        if stripped_rule and not stripped_rule.startswith('#'):
            yield stripped_rule
