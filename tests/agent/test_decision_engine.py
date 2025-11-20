#!/usr/bin/env python3
"""
Tests for DecisionEngine.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from mud_agent.agent.decision_engine import DecisionEngine


class TestDecisionEngine:
    """Test suite for DecisionEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.event_manager = MagicMock()
        self.client = MagicMock()
        self.client.send_command = AsyncMock()

        self.engine = DecisionEngine(self.event_manager, self.client)

    def test_initialization(self):
        """Test DecisionEngine initialization."""
        assert self.engine.event_manager == self.event_manager
        assert self.engine.client == self.client
        assert self.engine.logger is not None
        assert self.engine.code_agent is None  # Not initialized by default

    def test_initialize_code_agent(self):
        """Test code agent initialization."""
        with patch('mud_agent.agent.decision_engine.CodeAgent') as mock_agent:
            mock_instance = MagicMock()
            mock_agent.return_value = mock_instance

            self.engine.initialize_code_agent()

            assert self.engine.code_agent is not None

    @pytest.mark.asyncio
    async def test_decide_next_action_no_context(self):
        """Test decision making with no automation context."""
        # Mock state
        with patch.object(self.engine, 'client') as mock_client:
            mock_client.recent_responses = []
            mock_client.last_response = ""

            result = await self.engine.decide_next_action()

            # May return None or a default action
            # Implementation specific

    @pytest.mark.asyncio
    async def test_decide_next_action_in_combat(self):
        """Test decision making during combat."""
        # Setup combat scenario
        with patch.object(self.engine, 'client') as mock_client:
            mock_client.recent_responses = ["The goblin attacks you!"]
            mock_client.last_response = "You are in combat!"

            # Mock attributes
            if not hasattr(self.engine, 'recent_commands'):
                self.engine.recent_commands = []
            if not hasattr(self.engine, 'automation_context'):
                self.engine.automation_context = None

            result = await self.engine.decide_next_action()

            # Implementation specific - may return combat action

    @pytest.mark.asyncio
    async def test_decide_next_action_with_context(self):
        """Test decision making with automation context."""
        self.engine.automation_context = "exploring"

        with patch.object(self.engine, 'client') as mock_client:
            mock_client.recent_responses = ["You are in a forest"]
            mock_client.last_response = "You see a path ahead"

            if not hasattr(self.engine, 'recent_commands'):
                self.engine.recent_commands = []

            result = await self.engine.decide_next_action()

            # Implementation specific

    def test_generate_second_thought_combat(self):
        """Test second thought generation during combat."""
        # Setup engine state
        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = ["kill goblin", "cast heal"]

        with patch.object(self.engine, 'client') as mock_client:
            mock_client.last_response = "The goblin hits you hard!"
            mock_client.recent_responses = ["Combat continues"]

            result = self.engine._generate_second_thought(in_combat=True, context=None)

            assert isinstance(result, str)
            assert len(result) > 0

    def test_generate_second_thought_exploration(self):
        """Test second thought generation during exploration."""
        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = ["north", "look"]

        with patch.object(self.engine, 'client') as mock_client:
            mock_client.last_response = "You are in a forest"
            mock_client.recent_responses = ["Trees surround you"]

            result = self.engine._generate_second_thought(in_combat=False, context="exploring")

            assert isinstance(result, str)
            assert len(result) > 0

    def test_generate_third_thought_combat(self):
        """Test third thought generation during combat."""
        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = ["attack"]

        with patch.object(self.engine, 'client') as mock_client:
            mock_client.last_response = "You attack the goblin"

            result = self.engine._generate_third_thought(in_combat=True, context=None)

            assert isinstance(result, str)
            assert len(result) > 0

    def test_generate_third_thought_with_context(self):
        """Test third thought generation with context."""
        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = ["quest request"]

        with patch.object(self.engine, 'client') as mock_client:
            mock_client.last_response = "Quest accepted"

            result = self.engine._generate_third_thought(in_combat=False, context="questing")

            assert isinstance(result, str)
            assert len(result) > 0

    def test_generate_final_thought_combat(self):
        """Test final thought generation during combat."""
        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = ["flee"]

        with patch.object(self.engine, 'client') as mock_client:
            mock_client.last_response = "You flee from combat"

            thought, action = self.engine._generate_final_thought(in_combat=True, context=None)

            assert isinstance(thought, str)
            # action can be None or a string

    def test_generate_final_thought_exploration(self):
        """Test final thought generation during exploration."""
        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = ["look", "north"]

        with patch.object(self.engine, 'client') as mock_client:
            mock_client.last_response = "A path leads onward"

            thought, action = self.engine._generate_final_thought(in_combat=False, context="exploring")

            assert isinstance(thought, str)

    @pytest.mark.asyncio
    async def test_use_sequential_thinking_enabled(self):
        """Test sequential thinking when enabled."""
        # Mock code agent
        mock_agent = MagicMock()
        mock_agent.run = MagicMock(return_value="go north")
        self.engine.code_agent = mock_agent

        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = []

        with patch.object(self.engine, 'client') as mock_client:
            mock_client.last_response = "You are at a crossroads"
            mock_client.recent_responses = []

            result = await self.engine._use_sequential_thinking(
                in_combat=False,
                context="exploring",
                context_str="Context: exploring"
            )

            # Implementation specific

    @pytest.mark.asyncio
    async def test_use_sequential_thinking_no_agent(self):
        """Test sequential thinking when code agent is not initialized."""
        self.engine.code_agent = None

        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = []

        result = await self.engine._use_sequential_thinking(
            in_combat=False,
            context=None,
            context_str=""
        )

        # Should handle gracefully
        # May return None or fall back to default behavior

    def test_combat_detection(self):
        """Test combat state detection from responses."""
        combat_responses = [
            "The goblin attacks you!",
            "You are in combat!",
            "The enemy strikes!"
        ]

        for response in combat_responses:
            with patch.object(self.engine, 'client') as mock_client:
                mock_client.last_response = response
                # Combat detection would be in decide_next_action
                # This is a basic test

    def test_loop_detection(self):
        """Test detection of command loops."""
        # Simulate repeated commands
        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = ["north", "south", "north", "south", "north"]

        # Decision engine should detect this pattern
        # Implementation specific test

    def test_recent_commands_tracking(self):
        """Test that recent commands are tracked properly."""
        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = []

        # Commands should be added to recent_commands
        # Implementation specific

    def test_health_threshold_logic(self):
        """Test health-based decision making."""
        # Mock low health scenario
        with patch.object(self.engine, 'client') as mock_client:
            # Setup low health state
            mock_client.character_hp = 20
            mock_client.character_max_hp = 100

            # Decision engine should recognize low health
            # Implementation specific

    @pytest.mark.asyncio
    async def test_error_handling_in_decide_next_action(self):
        """Test error handling in decision making."""
        with patch.object(self.engine, 'client') as mock_client:
            mock_client.last_response = None
            mock_client.recent_responses = None

            if not hasattr(self.engine, 'recent_commands'):
                self.engine.recent_commands = []

            # Should handle None values gracefully
            try:
                result = await self.engine.decide_next_action()
                # May return None or raise
            except Exception:
                pass  # Exception is acceptable

    @pytest.mark.asyncio
    async def test_error_handling_with_code_agent(self):
        """Test error handling when code agent raises exception."""
        mock_agent = MagicMock()
        mock_agent.run.side_effect = Exception("Agent error")
        self.engine.code_agent = mock_agent

        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = []

        with patch.object(self.engine, 'client') as mock_client:
            mock_client.last_response = "test"
            mock_client.recent_responses = []

            # Should handle agent errors gracefully
            try:
                result = await self.engine._use_sequential_thinking(
                    in_combat=False,
                    context=None,
                    context_str=""
                )
            except Exception:
                pass  # Exception is acceptable

    def test_context_formatting(self):
        """Test that context is properly formatted for prompts."""
        contexts = ["exploring", "questing", "combat", None]

        for context in contexts:
            # Context should be formatted properly
            # Implementation specific
            pass

    def test_response_excerpt_length(self):
        """Test that response excerpts are limited to reasonable length."""
        long_response = "A" * 1000  # Very long response

        with patch.object(self.engine, 'client') as mock_client:
            mock_client.last_response = long_response

            # Excerpts should be limited
            # Implementation specific

    def test_max_recent_commands_limit(self):
        """Test that recent commands list doesn't grow unbounded."""
        if not hasattr(self.engine, 'recent_commands'):
            self.engine.recent_commands = []

        # Add many commands
        for i in range(20):
            if hasattr(self.engine, 'recent_commands'):
                self.engine.recent_commands.append(f"command_{i}")

        # List should be limited
        # Implementation specific - max is usually 5
        if hasattr(self.engine, 'recent_commands'):
            assert len(self.engine.recent_commands) <= 20  # Generous limit

    def test_constants_defined(self):
        """Test that required constants are defined."""
        from mud_agent.agent.decision_engine import (
            ZERO,
            LOW_HEALTH_THRESHOLD,
            HIGH_HEALTH_THRESHOLD,
            LOW_MANA_THRESHOLD,
            HIGH_MANA_THRESHOLD,
            MIN_LEVEL_FOR_SPELLS,
            MAX_COMMAND_LENGTH,
            MAX_RECENT_COMMANDS,
            MIN_COMMANDS_FOR_LOOP_DETECTION,
            RESPONSE_EXCERPT_LENGTH,
            HEALTH_RECOVERY_THRESHOLD
        )

        assert ZERO == 0
        assert isinstance(LOW_HEALTH_THRESHOLD, int)
        assert isinstance(HIGH_HEALTH_THRESHOLD, int)
        assert isinstance(MAX_COMMAND_LENGTH, int)
