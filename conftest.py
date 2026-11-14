"""Put every topic folder (e.g. ``01-solid/``) on the import path.

Folder names start with a number, so they can't be imported as packages themselves.
Instead, each topic holds a normally named package that its tests import directly.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent

for topic_dir in sorted(ROOT.glob("[0-9][0-9]-*")):
    if topic_dir.is_dir():
        sys.path.insert(0, str(topic_dir))
