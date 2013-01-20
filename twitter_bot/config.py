#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ConfigParser


class Config(object):
    def __init__(self, config_file, section=None):
        self._config_file = config_file
        self._section = section

        self._config = ConfigParser.SafeConfigParser()
        self._config.read(config_file)

    @property
    def config_file(self):
        return self._config_file

    @property
    def section(self):
        return self._section

    @property
    def config(self):
        return self._config

    def get_value(self, key, section=None):
        section = section or self.section
        if not section:
            raise Exception('Section is not specified')
        return self.config.get(section, key)
