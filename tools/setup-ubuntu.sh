#!/usr/bin/env bash
# Compatibility entrypoint; dependency selection now covers all three families.
set -euo pipefail
exec /usr/bin/python3 "$(dirname "$0")/setup-linux.py" "$@"
