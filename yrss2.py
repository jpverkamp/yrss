#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

logging.basicConfig(format='[%(levelname)s] %(funcName)s: %(message)s', level = logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

import models
import server

# TODO: update thread

if __name__ == '__main__':
    server.app.run(debug = True)
