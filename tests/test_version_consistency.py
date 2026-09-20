"""Version consistency basic test (family simplified).

Verify:
- No hardcoded old version (0.1.0 / 0.0.1) in source code
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_no_hardcoded_old_version():
    old_patterns = [r'version\s*=\s*["\']0\.1\.0["\']', r'version\s*=\s*["\']0\.0\.1["\']']

    offenders = []
    for pyfile in PROJECT_ROOT.rglob("*.py"):
        if any(skip in str(pyfile) for skip in [".venv", "__pycache__", "node_modules", "backups"]):
            continue
        try:
            content = pyfile.read_text(encoding="utf-8", errors="ignore")
            for pat in old_patterns:
                if re.search(pat, content):
                    offenders.append(str(pyfile.relative_to(PROJECT_ROOT)))
                    break
        except Exception:
            pass

    assert offenders == []
