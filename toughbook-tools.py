#!/usr/bin/python3
"""Unified launcher and per-user installer for Toughbook Fedora Tools. SPDX-License-Identifier: MIT"""
import argparse
from contextlib import redirect_stdout
import io
import json
import sys

from toughbook.common import ToolError, desktop_user
from toughbook import integration


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page', choices=('overview', 'screen', 'audio', 'buttons'), default='overview')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--status', action='store_true', help='Print installation and feature status as JSON')
    modes.add_argument('--install', action='store_true', help='Install the unified app for this user')
    modes.add_argument('--uninstall', action='store_true', help='Remove app and helper integration; retain settings and backups')
    args = parser.parse_args(argv)
    try:
        desktop_user()
        if args.status:
            from toughbook import buttons
            result = {'app': integration.status()}
            for key, module in (('screen', 'screen'), ('audio', 'audio')):
                try:
                    from importlib import import_module
                    output = io.StringIO()
                    with redirect_stdout(output):
                        code = import_module('toughbook.' + module).main(['--status'])
                    result[key] = json.loads(output.getvalue()) if code == 0 else {'error': f'status exited {code}'}
                except Exception as exc:
                    result[key] = {'error': str(exc)}
            try:
                result['buttons'] = buttons.status()
            except Exception as exc:
                result['buttons'] = {'error': str(exc)}
            print(json.dumps(result, indent=2))
            return 0
        if args.install:
            integration.install_app(args.page)
            print('Installed Toughbook Tools in your application menu.')
            return 0
        if args.uninstall:
            integration.uninstall_app()
            print('Removed Toughbook Tools and button helper integration; user settings and backups were retained.')
            return 0
        from toughbook.gui import run_gui
        return run_gui(args.page)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f'Toughbook Tools: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
