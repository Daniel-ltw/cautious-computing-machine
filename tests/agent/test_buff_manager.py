#!/usr/bin/env python3
"""Tests for BuffManager."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from mud_agent.agent.buff_manager import BuffManager


class TestBuffManagerPatternDetection:
    """Test buff expiry pattern detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = False
        self.buff_manager = BuffManager(self.agent)

    def test_initialization(self):
        """Test BuffManager initializes with correct defaults."""
        assert self.buff_manager.agent == self.agent
        assert self.buff_manager.active is False
        assert self.buff_manager._recast_pending is False

    def test_detects_sanctuary_fades(self):
        """Test detection of sanctuary expiry."""
        assert self.buff_manager._check_buff_expiry("Your sanctuary fades.") is True

    def test_detects_no_longer_hidden(self):
        """Test detection of hide expiry."""
        assert self.buff_manager._check_buff_expiry("You are no longer hidden.") is True

    def test_detects_generic_wears_off(self):
        """Test detection of generic wear-off message."""
        assert self.buff_manager._check_buff_expiry("Your armor spell wears off.") is True

    def test_ignores_normal_text(self):
        """Test that normal game text is not detected as buff expiry."""
        assert self.buff_manager._check_buff_expiry("A rat attacks you!") is False

    def test_ignores_empty_text(self):
        """Test that empty text is not detected."""
        assert self.buff_manager._check_buff_expiry("") is False

    def test_detects_case_insensitive(self):
        """Test case-insensitive matching."""
        assert self.buff_manager._check_buff_expiry("YOUR SANCTUARY FADES.") is True
