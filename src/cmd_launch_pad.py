import logging
import re
import subprocess

from chromalog.mark.helpers.simple import success, error, important

logger = logging.getLogger()


class CmdLaunchPad:
    def __init__(self, cmd_template, dry_run=False):
        self.cmd_template = self._normalize_cmd_substitution_token(cmd_template)
        self.dry_run = dry_run

    def _normalize_cmd_substitution_token(self, cmd_template):
        '''Normalize the token to {}. cmd can hold '{}' or "{}" or {}'''
        return re.sub('\'\{\}\'|"\{\}"', '{}', cmd_template)

    def fire(self, parameter=''):
        '''Run the command after replacing every occurrence
        of {} with `parameter`'''
        cmd = self.cmd_template.replace('{}', parameter)
        logging.info('Run <{}>'.format(cmd))

        if not self.dry_run:
            # XXX this is blocking
            status, output = subprocess.getstatusoutput(cmd)
            if status:
                logger.error('Error: {}'.format(output))
            else:
                logger.info('Output: {}'.format(output))
