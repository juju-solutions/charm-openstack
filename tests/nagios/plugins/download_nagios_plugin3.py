#!/usr/bin/env python3

import os.path
import sys
import urllib.request
from glob import glob

MODULE_NAME = "nagios_plugin3.py"
MODULE_URL = os.path.join("https://git.launchpad.net/nrpe-charm/plain/files",
                          MODULE_NAME)
_cache = None


def content():
    global _cache
    if _cache is None:
        _cache = urllib.request.urlopen(MODULE_URL).read()
    assert len(_cache) > 0
    return _cache


def main(env_path):
    for i in glob(os.path.join(env_path, "lib/python3*", "site-packages")):
        mod_path = os.path.join(i, MODULE_NAME)
        if os.path.isdir(i) and not os.path.exists(mod_path):
            open(mod_path, "wb").write(content())


if __name__ == "__main__":
    main(sys.argv[1])
