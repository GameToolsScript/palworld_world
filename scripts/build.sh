#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_COMMAND="${PYTHON_COMMAND:-python3}"
OUTPUT_DIR="${1:-$PROJECT_ROOT/dist/linux-x86_64}"
VENV_ROOT="$PROJECT_ROOT/.venv-build"
VENV_PYTHON="$VENV_ROOT/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  "$PYTHON_COMMAND" -m venv "$VENV_ROOT"
fi

"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$PROJECT_ROOT/tools/requirements-build.txt"

if [[ -n "${EXTRA_PIP_PACKAGES:-}" ]]; then
  # Linux 等平台可以通过环境变量补充额外的构建依赖。
  # shellcheck disable=SC2206
  EXTRA_PACKAGES=( ${EXTRA_PIP_PACKAGES} )
  "$VENV_PYTHON" -m pip install "${EXTRA_PACKAGES[@]}"
fi

"$VENV_PYTHON" \
  "$PROJECT_ROOT/tools/build_palworld_parser.py" \
  --output-dir "$OUTPUT_DIR" \
  --binary-name "palworld-save-analysis" \
  --clean

echo "构建完成: $OUTPUT_DIR"
