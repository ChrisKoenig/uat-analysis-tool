"""
Pytest Configuration
=====================

Shared fixtures and configuration for triage tests.
"""

import pytest
import sys
import os

# Ensure the project root is on the Python path so that
# 'import triage' works correctly during test runs.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
