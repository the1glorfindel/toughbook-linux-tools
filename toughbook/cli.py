"""Consistent CLI errors without tracebacks for normal failures. SPDX-License-Identifier: MIT"""
import sys
from .common import ToolError


def dispatch(main):
    try:
        return main()
    except (KeyboardInterrupt, EOFError):
        print('Cancelled. Any incomplete transaction was rolled back.', file=sys.stderr)
        return 130
    except (ToolError, OSError, ValueError, KeyError, ImportError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    except Exception as exc:
        # D-Bus errors are imported lazily so --help works without desktop bindings.
        print(f'Error: {exc}. Inspect the session/dependencies and retained backup.', file=sys.stderr)
        return 1
