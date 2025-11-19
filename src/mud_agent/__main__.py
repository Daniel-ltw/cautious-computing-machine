#!/usr/bin/env python3
"""
Main entry point for the MUD agent package.

This allows the package to be run with `python -m mud_agent`.
"""

import asyncio
import sys

from .__main__textual_reactive import main

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
