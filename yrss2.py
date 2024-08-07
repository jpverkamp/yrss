#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import threading
import time
import os

logging.basicConfig(format='[%(levelname)s] %(funcName)s: %(message)s', level = logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

import models
import server

# Ask each user to update once per ten minutes
if 'YRSS_DEBUG' in os.environ:
    logging.info('Running in debug mode, skipping update thread')
else:
    def update_thread():
        while True:
            logging.info('Checking feeds for updates')
            for feed in models.Feed().select():
                try:
                    feed.refresh()
                except Exception as ex:
                    logging.warning(f'Exception in refresh loop ({ex})')

            time.sleep(10 * 60)

    threading.Thread(target = update_thread, daemon = True).start()

if __name__ == '__main__':
    server.app.run(host = '0.0.0.0', debug=True)
