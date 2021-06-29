from unittest.mock import patch

import charms.unit_test


charms.unit_test.patch_reactive()
charms.unit_test.patch_module('subprocess')
charms.unit_test.patch_module('urllib.request')
patch('time.sleep').start()
