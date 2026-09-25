#!/usr/bin/env bash
# Cloud Agent / Linux development bootstrap for the classroom gateway.
#
# The portable Windows release ships its own Python 3.11 runtime. For local
# development and automated tests we install only the dependencies that the
# gateway service, the Open WebUI bridge modules, and the pytest suite import,
# pinned to the versions recorded in requirements-runtime.lock. The heavy
# Open WebUI runtime (torch, chromadb, ...) is intentionally left out because
# the unit tests mock those boundaries; only the native probes need it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Dependencies the test suite and standalone gateway actually import, pinned to
# the portable runtime inventory (requirements-runtime.lock) plus the build lock
# (requirements-build.lock) for pytest.
python3 -m pip install --user --break-system-packages \
  "pytest==9.1.1" \
  "fastapi==0.136.3" \
  "starlette==1.6.0" \
  "httpx==0.28.1" \
  "pillow==12.2.0" \
  "uvicorn==0.51.0" \
  "pydantic==2.13.4" \
  "tzlocal==5.4.4"

# The tests and gateway import the repository as the top-level ``classroom``
# package (e.g. ``from classroom.app.classroom_service import ...``). The
# checkout directory is not named ``classroom``, so expose it through a stable
# symlink and register that root on the Python path via a .pth file. This keeps
# the checkout untouched and self-heals if the checkout path changes.
PYROOT="$HOME/.classroom-pyroot"
mkdir -p "$PYROOT"
ln -sfn "$REPO_ROOT" "$PYROOT/classroom"

USER_SITE="$(python3 -m site --user-site)"
mkdir -p "$USER_SITE"
printf '%s\n' "$PYROOT" > "$USER_SITE/classroom_pyroot.pth"

# Fail fast if the import wiring is wrong.
python3 -c "import classroom.app.classroom_service as s; print('classroom import OK:', s.ClassroomService.__name__)"

echo "Classroom gateway dev environment ready. Run the tests with: python3 -m pytest tests/"
