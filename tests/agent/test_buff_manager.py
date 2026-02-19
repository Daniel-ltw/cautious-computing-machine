#!/usr/bin/env python3
"""Tests for BuffManager."""

from unittest.mock import AsyncMock, MagicMock

import pytest

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
        assert (
            self.buff_manager._check_buff_expiry("Your armor spell wears off.") is True
        )

    def test_ignores_normal_text(self):
        """Test that normal game text is not detected as buff expiry."""
        assert self.buff_manager._check_buff_expiry("A rat attacks you!") is False

    def test_ignores_empty_text(self):
        """Test that empty text is not detected."""
        assert self.buff_manager._check_buff_expiry("") is False

    def test_detects_case_insensitive(self):
        """Test case-insensitive matching."""
        assert self.buff_manager._check_buff_expiry("YOUR SANCTUARY FADES.") is True


class TestBuffManagerRecast:
    """Test recast logic and debounce."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = False
        self.buff_manager = BuffManager(self.agent)
        self.buff_manager.active = True

    @pytest.mark.asyncio
    async def test_request_recast_sends_spellup(self):
        """Test that _request_recast sends spellup learned."""
        await self.buff_manager._request_recast()
        self.agent.send_command.assert_called_once_with("spellup learned")

    @pytest.mark.asyncio
    async def test_on_buff_expired_triggers_debounced_recast(self):
        """Test that buff expiry triggers a debounced recast."""
        self.buff_manager._on_buff_expired("sanctuary")
        assert self.buff_manager._debounce_task is not None
        await self.buff_manager._debounce_task
        self.agent.send_command.assert_called_once_with("spellup learned")

    @pytest.mark.asyncio
    async def test_multiple_expiries_produce_single_recast(self):
        """Test that rapid expiries are debounced into one recast."""
        self.buff_manager._on_buff_expired("sanctuary")
        self.buff_manager._on_buff_expired("shield")
        self.buff_manager._on_buff_expired("armor")
        await self.buff_manager._debounce_task
        self.agent.send_command.assert_called_once_with("spellup learned")

    @pytest.mark.asyncio
    async def test_no_recast_when_inactive(self):
        """Test that no recast happens when buff manager is inactive."""
        self.buff_manager.active = False
        self.buff_manager._on_buff_expired("sanctuary")
        assert self.buff_manager._debounce_task is None
        self.agent.send_command.assert_not_called()


class TestBuffManagerCombatAwareness:
    """Test combat-aware recast deferral."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = True  # Start in combat
        self.buff_manager = BuffManager(self.agent)
        self.buff_manager.active = True

    @pytest.mark.asyncio
    async def test_expiry_during_combat_sets_pending(self):
        """Test that expiry during combat defers recast."""
        self.buff_manager._on_buff_expired("sanctuary")
        # No debounce task created during combat
        assert self.buff_manager._debounce_task is None
        self.agent.send_command.assert_not_called()
        assert self.buff_manager._recast_pending is True

    @pytest.mark.asyncio
    async def test_combat_ended_triggers_pending_recast(self):
        """Test that pending recast fires when combat ends."""
        # Expire during combat
        self.buff_manager._on_buff_expired("sanctuary")
        assert self.buff_manager._recast_pending is True

        # Combat ends
        self.agent.combat_manager.in_combat = False
        self.buff_manager._on_combat_state_changed()
        await self.buff_manager._debounce_task
        self.agent.send_command.assert_called_once_with("spellup learned")
        assert self.buff_manager._recast_pending is False

    @pytest.mark.asyncio
    async def test_combat_ended_no_pending_does_nothing(self):
        """Test that combat end without pending recast does nothing."""
        self.agent.combat_manager.in_combat = False
        self.buff_manager._on_combat_state_changed()
        self.agent.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_combat_ended_inactive_clears_pending_no_recast(self):
        """Test that combat end on inactive manager clears pending but doesn't recast."""
        # Expire during combat
        self.buff_manager._on_buff_expired("sanctuary")
        assert self.buff_manager._recast_pending is True

        # Deactivate manager, then combat ends
        self.buff_manager.active = False
        self.agent.combat_manager.in_combat = False
        self.buff_manager._on_combat_state_changed()
        # Pending should be cleared
        assert self.buff_manager._recast_pending is False
        # But no recast should fire
        assert self.buff_manager._debounce_task is None
        self.agent.send_command.assert_not_called()


class TestBuffManagerEventHandling:
    """Test data event handling and incoming text processing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = False
        self.buff_manager = BuffManager(self.agent)
        self.buff_manager.active = True

    @pytest.mark.asyncio
    async def test_handle_incoming_data_detects_expiry(self):
        """Test that incoming data with expiry text triggers recast."""
        self.buff_manager._handle_incoming_data("Your sanctuary fades.")
        assert self.buff_manager._debounce_task is not None
        await self.buff_manager._debounce_task
        self.agent.send_command.assert_called_once_with("spellup learned")

    @pytest.mark.asyncio
    async def test_handle_incoming_data_ignores_normal_text(self):
        """Test that normal text doesn't trigger recast."""
        self.buff_manager._handle_incoming_data("A rat scurries by.")
        assert self.buff_manager._debounce_task is None
        self.agent.send_command.assert_not_called()

    def test_handle_incoming_data_when_inactive(self):
        """Test that inactive manager ignores all text."""
        self.buff_manager.active = False
        self.buff_manager._handle_incoming_data("Your sanctuary fades.")
        assert self.buff_manager._debounce_task is None


class TestBuffManagerLifecycle:
    """Test start/stop lifecycle."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = False
        self.buff_manager = BuffManager(self.agent)

    @pytest.mark.asyncio
    async def test_setup_subscribes_to_events(self):
        """Test that setup subscribes to client data events."""
        await self.buff_manager.setup()
        self.agent.client.events.on.assert_called_once_with(
            "data", self.buff_manager._handle_incoming_data
        )

    @pytest.mark.asyncio
    async def test_start_activates_and_starts_fallback(self):
        """Test that start activates manager and starts fallback timer."""
        await self.buff_manager.start()
        assert self.buff_manager.active is True
        assert self.buff_manager._fallback_task is not None
        await self.buff_manager.stop()

    @pytest.mark.asyncio
    async def test_stop_deactivates_and_cancels_tasks(self):
        """Test that stop deactivates and cleans up all tasks."""
        await self.buff_manager.start()
        await self.buff_manager.stop()
        assert self.buff_manager.active is False
        assert self.buff_manager._recast_pending is False

    @pytest.mark.asyncio
    async def test_stop_when_not_active(self):
        """Test that stop is safe to call when not active."""
        await self.buff_manager.stop()
        assert self.buff_manager.active is False
