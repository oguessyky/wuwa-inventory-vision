# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Module entry point: ``python -m wuwa_vision``.

The generated ``wuwa.exe`` console shim is an unsigned executable, which
Windows Application Control (Smart App Control / WDAC) blocks outright on
some machines. Running the package as a module goes through the signed
interpreter instead and needs no shim.
"""

import sys

from wuwa_vision.cli import main

if __name__ == "__main__":
    sys.exit(main())
