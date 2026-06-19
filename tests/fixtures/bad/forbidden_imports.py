from __future__ import annotations

import os
import subprocess

import requests


def run() -> None:
    os.system("echo nope")
    subprocess.run(["ls"])
    requests.get("https://example.com")
