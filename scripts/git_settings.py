#!/usr/bin/env python3
"""Script for checking git settings."""
# ruff: noqa: T201

import subprocess

filemode = subprocess.run(
    ["git", "config", "--get", "core.filemode"], capture_output=True, check=False
)
autocrlf = subprocess.run(
    ["git", "config", "--get", "core.autocrlf"], capture_output=True, check=False
)

# filemode should be set to false
if filemode.returncode != 0:
    print("filemode not set")
elif filemode.stdout.decode("utf8").rstrip() != "false":
    print("Not correct filemode")

# autocrlf should be set to input
if autocrlf.returncode != 0:
    print("autocrlf not set")
elif autocrlf.stdout.decode("utf8").rstrip() != "input":
    print("Not correct autocrlf")
    print(autocrlf.stdout.decode("utf8"))
