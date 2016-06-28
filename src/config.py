#!/usr/bin/env python
# *-* encoding: utf-8 *-*

import toml


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

    rules = data.get('rules')
    if rules and isinstance(rules, str):
        data['rules'] = list(_parse_rules_string(rules))

    return data


def _parse_rules_string(rules_string):
    for rule in rules_string.split('\n'):
        stripped_rule = rule.strip()
        if stripped_rule and not stripped_rule.startswith('#'):
            yield stripped_rule
