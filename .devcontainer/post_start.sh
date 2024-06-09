#!/usr/bin/env bash

set -euo pipefail

# Change to project root
cd "$(dirname "$0")/.."

# Git settings
git config --global core.filemode false
git config --global core.autocrlf input

# Check that all versions correlates
python ./scripts/versions.py -c