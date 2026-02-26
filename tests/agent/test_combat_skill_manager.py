#!/usr/bin/env python3
"""Tests for CombatSkillManager."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from mud_agent.agent.combat_skill_manager import CombatSkillManager


def make_agent(
    opener_skills=None,
    rotation_skills=None,
    flee_threshold=0.25,
    flee_command="flee",
    in_combat=False,
    hp_current=100,
    hp_max=100,
):
    """Create a mock agent with configurable combat settings."""
    agent = MagicMock()
    agent.send_command = AsyncMock()
    agent.client = MagicMock()
    agent.client.events = MagicMock()
    agent.combat_manager = MagicMock()
    agent.combat_manager.in_combat = in_combat
    agent.state_manager = MagicMock()
    agent.state_manager.hp_current = hp_current
    agent.state_manager.hp_max = hp_max
    agent.config = MagicMock()
    agent.config.agent = MagicMock()
    agent.config.agent.combat_opener_skills = opener_skills or []
    agent.config.agent.combat_rotation_skills = rotation_skills or []
    agent.config.agent.combat_flee_threshold = flee_threshold
    agent.config.agent.combat_flee_command = flee_command
    return agent


class TestCombatSkillManagerInit:
    """Test CombatSkillManager initialization."""

    def test_defaults(self):
        """Test that the manager initializes with correct defaults."""
        agent = make_agent()
        mgr = CombatSkillManager(agent)
        assert mgr.agent is agent
        assert mgr.active is False
        assert mgr.state == "IDLE"

    def test_enabled_with_opener_skills(self):
        """Test enabled is True when opener skills are configured."""
        agent = make_agent(opener_skills=["backstab"])
        mgr = CombatSkillManager(agent)
        assert mgr.enabled is True

    def test_enabled_with_rotation_skills(self):
        """Test enabled is True when rotation skills are configured."""
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        assert mgr.enabled is True

    def test_disabled_no_skills(self):
        """Test enabled is False when no skills are configured."""
        agent = make_agent()
        mgr = CombatSkillManager(agent)
        assert mgr.enabled is False

    def test_enabled_with_both_skills(self):
        """Test enabled is True when both opener and rotation skills are configured."""
        agent = make_agent(opener_skills=["backstab"], rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        assert mgr.enabled is True


class TestCombatSkillManagerLifecycle:
    """Test setup/start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_setup_subscribes_to_events(self):
        """Test that setup subscribes to client data events."""
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        await mgr.setup()
        agent.client.events.on.assert_called_once_with(
            "data", mgr._handle_incoming_data
        )

    @pytest.mark.asyncio
    async def test_setup_skips_when_disabled(self):
        """Test that setup does not subscribe when no skills configured."""
        agent = make_agent()
        mgr = CombatSkillManager(agent)
        await mgr.setup()
        agent.client.events.on.assert_not_called()

    @pytest.mark.asyncio
    async def test_setup_handles_missing_client(self):
        """Test that setup handles missing client gracefully."""
        agent = MagicMock(spec=[])
        agent.config = MagicMock()
        agent.config.agent = MagicMock()
        agent.config.agent.combat_opener_skills = ["backstab"]
        agent.config.agent.combat_rotation_skills = []
        mgr = CombatSkillManager(agent)
        await mgr.setup()  # Should not raise

    @pytest.mark.asyncio
    async def test_start_activates(self):
        """Test that start sets active=True and resets state."""
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        await mgr.start()
        assert mgr.active is True
        assert mgr.state == "IDLE"

    @pytest.mark.asyncio
    async def test_stop_deactivates(self):
        """Test that stop sets active=False and resets state."""
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        await mgr.start()
        await mgr.stop()
        assert mgr.active is False
        assert mgr.state == "IDLE"

    @pytest.mark.asyncio
    async def test_stop_cancels_pending_task(self):
        """Test that stop cancels any pending round task."""
        agent = make_agent(rotation_skills=["kick"], in_combat=True)
        mgr = CombatSkillManager(agent)
        await mgr.start()
        # Create a pending task
        mgr._schedule_round()
        assert mgr._pending_round_task is not None
        await mgr.stop()
        assert mgr._pending_round_task is None

    @pytest.mark.asyncio
    async def test_stop_safe_when_not_started(self):
        """Test that stop is safe to call without start."""
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        await mgr.stop()  # Should not raise
        assert mgr.active is False


class TestCombatSkillManagerRoundDetection:
    """Test combat round pattern detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = make_agent(rotation_skills=["kick"])
        self.mgr = CombatSkillManager(self.agent)

    def test_detects_you_hit(self):
        assert self.mgr._is_combat_round("You hit the goblin with your sword.") is True

    def test_detects_hits_you(self):
        assert self.mgr._is_combat_round("The goblin hits you with a club.") is True

    def test_detects_misses_you(self):
        assert self.mgr._is_combat_round("The goblin misses you.") is True

    def test_detects_you_miss(self):
        assert self.mgr._is_combat_round("You miss the goblin.") is True

    def test_detects_you_dodge(self):
        assert self.mgr._is_combat_round("You dodge the attack.") is True

    def test_detects_dodges_your(self):
        assert self.mgr._is_combat_round("The goblin dodges your attack.") is True

    def test_detects_you_parry(self):
        assert self.mgr._is_combat_round("You parry the blow.") is True

    def test_detects_parries_your(self):
        assert self.mgr._is_combat_round("The goblin parries your attack.") is True

    def test_detects_your_attack(self):
        assert self.mgr._is_combat_round("Your attack devastates the goblin!") is True

    def test_detects_attacks_you(self):
        assert self.mgr._is_combat_round("The goblin attacks you!") is True

    def test_case_insensitive(self):
        assert self.mgr._is_combat_round("YOU HIT the goblin!") is True

    def test_ignores_normal_text(self):
        assert self.mgr._is_combat_round("A bird sings in the distance.") is False

    def test_ignores_empty_text(self):
        assert self.mgr._is_combat_round("") is False


class TestCombatSkillManagerStateTransitions:
    """Test state machine transitions."""

    @pytest.mark.asyncio
    async def test_idle_to_opening_to_rotating(self):
        """Test full state progression: IDLE -> OPENING -> ROTATING."""
        agent = make_agent(
            opener_skills=["backstab", "circle"],
            rotation_skills=["kick"],
            in_combat=True,
        )
        mgr = CombatSkillManager(agent)
        await mgr.start()

        # First round: IDLE -> OPENING, sends first opener
        await mgr._on_combat_round()
        assert mgr.state == "OPENING"
        agent.send_command.assert_called_with("backstab")

        # Second round: still OPENING, sends second opener
        agent.send_command.reset_mock()
        await mgr._on_combat_round()
        assert mgr.state == "ROTATING"
        agent.send_command.assert_called_with("circle")

        # Third round: ROTATING, sends rotation skill
        agent.send_command.reset_mock()
        await mgr._on_combat_round()
        assert mgr.state == "ROTATING"
        agent.send_command.assert_called_with("kick")

    @pytest.mark.asyncio
    async def test_idle_to_rotating_no_openers(self):
        """Test IDLE -> ROTATING when no openers configured."""
        agent = make_agent(rotation_skills=["kick", "bash"], in_combat=True)
        mgr = CombatSkillManager(agent)
        await mgr.start()

        await mgr._on_combat_round()
        assert mgr.state == "ROTATING"
        agent.send_command.assert_called_with("kick")

    @pytest.mark.asyncio
    async def test_rotation_cycling(self):
        """Test that rotation skills cycle with modulo."""
        agent = make_agent(rotation_skills=["kick", "bash"], in_combat=True)
        mgr = CombatSkillManager(agent)
        await mgr.start()

        # Round 1: kick
        await mgr._on_combat_round()
        assert mgr.state == "ROTATING"
        agent.send_command.assert_called_with("kick")

        # Round 2: bash
        agent.send_command.reset_mock()
        await mgr._on_combat_round()
        agent.send_command.assert_called_with("bash")

        # Round 3: back to kick
        agent.send_command.reset_mock()
        await mgr._on_combat_round()
        agent.send_command.assert_called_with("kick")

    @pytest.mark.asyncio
    async def test_combat_end_resets_state(self):
        """Test that combat ending resets state and indices."""
        agent = make_agent(
            opener_skills=["backstab", "circle"],
            rotation_skills=["kick"],
            in_combat=True,
        )
        mgr = CombatSkillManager(agent)
        await mgr.start()

        # Go through first opener (still in OPENING since 2 openers)
        await mgr._on_combat_round()
        assert mgr.state == "OPENING"

        # Simulate combat end
        mgr._on_combat_ended()
        assert mgr.state == "IDLE"
        assert mgr._opener_index == 0
        assert mgr._rotation_index == 0

    @pytest.mark.asyncio
    async def test_not_active_skips_round(self):
        """Test that inactive manager skips round processing."""
        agent = make_agent(rotation_skills=["kick"], in_combat=True)
        mgr = CombatSkillManager(agent)
        # Not started, so active is False
        await mgr._on_combat_round()
        agent.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_in_combat_skips_round(self):
        """Test that being out of combat skips round processing."""
        agent = make_agent(rotation_skills=["kick"], in_combat=False)
        mgr = CombatSkillManager(agent)
        await mgr.start()
        await mgr._on_combat_round()
        agent.send_command.assert_not_called()


class TestCombatSkillManagerFleeThreshold:
    """Test flee behavior based on HP threshold."""

    @pytest.mark.asyncio
    async def test_flee_when_hp_low(self):
        """Test that manager sends flee when HP is below threshold."""
        agent = make_agent(
            rotation_skills=["kick"],
            flee_threshold=0.25,
            flee_command="flee",
            in_combat=True,
            hp_current=20,
            hp_max=100,
        )
        mgr = CombatSkillManager(agent)
        await mgr.start()

        await mgr._on_combat_round()
        assert mgr.state == "FLEEING"
        agent.send_command.assert_called_with("flee")

    @pytest.mark.asyncio
    async def test_no_flee_when_hp_high(self):
        """Test that manager does not flee when HP is above threshold."""
        agent = make_agent(
            rotation_skills=["kick"],
            flee_threshold=0.25,
            in_combat=True,
            hp_current=80,
            hp_max=100,
        )
        mgr = CombatSkillManager(agent)
        await mgr.start()

        await mgr._on_combat_round()
        assert mgr.state != "FLEEING"
        agent.send_command.assert_called_with("kick")

    @pytest.mark.asyncio
    async def test_fleeing_blocks_further_skills(self):
        """Test that FLEEING state blocks further skill execution."""
        agent = make_agent(
            rotation_skills=["kick"],
            flee_threshold=0.25,
            flee_command="flee",
            in_combat=True,
            hp_current=10,
            hp_max=100,
        )
        mgr = CombatSkillManager(agent)
        await mgr.start()

        # First round triggers flee
        await mgr._on_combat_round()
        assert mgr.state == "FLEEING"
        agent.send_command.assert_called_with("flee")

        # Second round: should not send any more commands (state is FLEEING)
        agent.send_command.reset_mock()
        await mgr._on_combat_round()
        agent.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_zero_max_hp_does_not_crash(self):
        """Test that zero max HP does not cause division by zero."""
        agent = make_agent(
            rotation_skills=["kick"],
            in_combat=True,
            hp_current=0,
            hp_max=0,
        )
        mgr = CombatSkillManager(agent)
        await mgr.start()

        await mgr._on_combat_round()
        # Should flee when max HP is 0 (can't determine health)
        assert mgr.state == "FLEEING"

    @pytest.mark.asyncio
    async def test_custom_flee_command(self):
        """Test that custom flee command is used."""
        agent = make_agent(
            rotation_skills=["kick"],
            flee_threshold=0.25,
            flee_command="recall",
            in_combat=True,
            hp_current=10,
            hp_max=100,
        )
        mgr = CombatSkillManager(agent)
        await mgr.start()

        await mgr._on_combat_round()
        agent.send_command.assert_called_with("recall")

    @pytest.mark.asyncio
    async def test_flee_at_exact_threshold(self):
        """Test flee triggers when HP ratio equals threshold exactly."""
        agent = make_agent(
            rotation_skills=["kick"],
            flee_threshold=0.25,
            in_combat=True,
            hp_current=25,
            hp_max=100,
        )
        mgr = CombatSkillManager(agent)
        await mgr.start()

        # HP ratio is exactly 0.25, which is NOT less than 0.25, so should not flee
        await mgr._on_combat_round()
        assert mgr.state != "FLEEING"


class TestCombatSkillManagerDebounce:
    """Test debounce behavior for rapid round messages."""

    @pytest.mark.asyncio
    async def test_rapid_rounds_fire_once(self):
        """Test that rapid round messages only fire skill once."""
        agent = make_agent(rotation_skills=["kick"], in_combat=True)
        mgr = CombatSkillManager(agent)
        await mgr.start()

        # Schedule multiple rounds rapidly
        mgr._schedule_round()
        mgr._schedule_round()
        mgr._schedule_round()

        # Wait for the debounce to complete
        task = mgr._pending_round_task
        assert task is not None
        await task

        # Only one skill should have been sent
        agent.send_command.assert_called_once_with("kick")

    @pytest.mark.asyncio
    async def test_second_round_after_debounce(self):
        """Test that a new round fires after previous debounce completes."""
        agent = make_agent(rotation_skills=["kick", "bash"], in_combat=True)
        mgr = CombatSkillManager(agent)
        await mgr.start()

        # First round
        mgr._schedule_round()
        await mgr._pending_round_task

        # Second round after debounce completed
        mgr._schedule_round()
        await mgr._pending_round_task

        assert agent.send_command.call_count == 2
        agent.send_command.assert_any_call("kick")
        agent.send_command.assert_any_call("bash")


class TestCombatSkillManagerEventHandling:
    """Test end-to-end event handling."""

    @pytest.mark.asyncio
    async def test_incoming_combat_text_triggers_skill(self):
        """Test that combat text in combat triggers skill execution."""
        agent = make_agent(rotation_skills=["kick"], in_combat=True)
        mgr = CombatSkillManager(agent)
        await mgr.start()

        mgr._handle_incoming_data("You hit the goblin with your sword.")
        assert mgr._pending_round_task is not None
        await mgr._pending_round_task
        agent.send_command.assert_called_with("kick")

    @pytest.mark.asyncio
    async def test_inactive_ignores_data(self):
        """Test that inactive manager ignores incoming data."""
        agent = make_agent(rotation_skills=["kick"], in_combat=True)
        mgr = CombatSkillManager(agent)
        # Not started
        mgr._handle_incoming_data("You hit the goblin with your sword.")
        assert mgr._pending_round_task is None
        agent.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_combat_end_detected_via_data(self):
        """Test that combat ending is detected from data events."""
        agent = make_agent(
            opener_skills=["backstab", "circle"],
            rotation_skills=["kick"],
            in_combat=True,
        )
        mgr = CombatSkillManager(agent)
        await mgr.start()

        # Process a combat round to change state from IDLE (2 openers, so stays in OPENING)
        mgr._handle_incoming_data("You hit the goblin.")
        await mgr._pending_round_task
        assert mgr.state == "OPENING"

        # Combat ends
        agent.combat_manager.in_combat = False
        mgr._handle_incoming_data("The goblin is dead!")
        assert mgr.state == "IDLE"
        assert mgr._opener_index == 0

    @pytest.mark.asyncio
    async def test_non_combat_text_in_combat_ignored(self):
        """Test that non-combat text during combat does not trigger skills."""
        agent = make_agent(rotation_skills=["kick"], in_combat=True)
        mgr = CombatSkillManager(agent)
        await mgr.start()

        mgr._handle_incoming_data("A bird sings in the distance.")
        assert mgr._pending_round_task is None
        agent.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_combat_text_out_of_combat_ignored(self):
        """Test that combat text when not in combat does not trigger skills."""
        agent = make_agent(rotation_skills=["kick"], in_combat=False)
        mgr = CombatSkillManager(agent)
        await mgr.start()

        mgr._handle_incoming_data("You hit the training dummy.")
        assert mgr._pending_round_task is None
        agent.send_command.assert_not_called()
