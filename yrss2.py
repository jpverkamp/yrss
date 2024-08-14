#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import threading
import time
import os

logging.basicConfig(
    format="[%(levelname)s] %(funcName)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

import models
import server

if "YRSS_API_KEY" not in os.environ:
    logging.error("YRSS_API_KEY environment variable is required")
    exit(1)

# Ask each user to update once per ten minutes
if os.environ.get("YRSS_DEBUG", "False").lower() == "true":
    logging.info("Running in debug mode, skipping update threads")
else:

    def prune_thread():
        """Thread to remove any unused feeds"""

        while True:
            logging.info("Pruning unused feeds")
            for feed in models.Feed().select():
                if not feed.is_used():
                    logging.info(f"Removing unused feed: {feed}")
                    feed.delete_instance(recursive=True)

                    # TODO: This will also delete filters for this feed, is this intentional?
                    # They're not currently subscribed, but may return and then the filters are gone

            time.sleep(24 * 60 * 60)

    threading.Thread(target=prune_thread, daemon=True).start()

    def update_thread():
        """Thread to update all feeds for all users"""

        while True:
            logging.info("Checking feeds for updates")
            for feed in models.Feed().select():
                try:
                    feed.refresh()
                except Exception as ex:
                    logging.warning(f"Exception in refresh loop ({ex})")

            time.sleep(10 * 60)

    threading.Thread(target=update_thread, daemon=True).start()

if __name__ == "__main__":
    server.app.run(host="0.0.0.0", debug=True, port=8001)
