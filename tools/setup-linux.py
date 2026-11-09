#!/usr/bin/env python3
"""Set up Toughbook Tools on Debian-based, Fedora and Arch-based Linux."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from toughbook.cli import dispatch
from toughbook.setup import main

if __name__ == '__main__':
    raise SystemExit(dispatch(main))
