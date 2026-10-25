# Phase 5 security review

Review date: 2026-10-25. This is evidence of checks performed, not a guarantee that software has no vulnerabilities.

- Gitleaks 8.30.1 scanned all 56 commits then present (through a3f1e54), approximately 1.10 MB of historical content, with redacted output. No leaks found. The release archive checksum matched the publisher's checksum file. Reports and binaries are in ignored `.cache/security`.
- `npm audit --omit=dev` found zero known production dashboard dependency vulnerabilities.
- `pip-audit --no-deps --disable-pip` checked pinned root, signals, backtest, research-agent, scheduler, alerts and browser lockfiles: no known vulnerabilities reported. The editable local shared package cannot be matched to a package-index advisory; its pinned dependencies are listed in the locks.
- News initially reported filelock and setuptools advisories. Updated to filelock 4.2.1 and setuptools 84.1.0, the reported fixed versions. All 25 news unit tests and the installed-package compatibility check passed. Repeated news audit found no known vulnerabilities in audited packages. The CPU-specific torch wheel was skipped by the PyPI audit; do not interpret that skip as a pass.
- Source release/advisory references: [filelock 4.2.1](https://pypi.org/project/filelock/4.2.1/), [Windows lock permissions advisory](https://github.com/tox-dev/filelock/security/advisories/GHSA-8mx5-7m5m-r77g), [setuptools releases](https://pypi.org/project/setuptools/).
- The Gemini key previously posted in chat and the Telegram token posted on 2026-10-25 require replacement. A clean Git scan does not undo exposure in chat. Replacement secrets must be entered only into the ignored local environment file. Telegram delivery remains disabled.
- Earlier owner-route tests passed anonymous denial, origin checks and owner authentication; earlier database advisors found no new database security findings. The existing leaked-password-protection warning remains. These checks have not yet been repeated as a final commissioning audit.

Remaining: local build output/log scanning, final database access review, restore verification, source-by-source permission review and runtime restart after dependency changes. Schedules remain disabled.
