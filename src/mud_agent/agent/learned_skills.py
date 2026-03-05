"""Learned skills provider.

Sends the 'learned' command to the MUD server, parses the tabular output,
and stores the resulting skill set for use by any manager (combat rotation,
mob hunt, etc.).
"""

import logging

logger = logging.getLogger(__name__)


def parse_learned_output(text: str) -> set[str]:
    """Parse the output of the 'learned' command to extract skill names.

    The learned output is a table where each data row has a skill name as
    the first column, followed by numeric columns (spell number, practice%,
    level learned). Header/separator lines and summary lines are skipped.

    Args:
        text: Raw response from the 'learned' MUD command.

    Returns:
        A set of lowercase skill names.
    """
    skills: set[str] = set()
    if not text:
        return skills

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip separator lines (dashes, equals, pipes only)
        if all(c in "-=+| " for c in line):
            continue
        # Skip header-like lines and summary lines
        lower = line.lower()
        if any(
            keyword in lower
            for keyword in [
                "skill",
                "spell",
                "practice",
                "level",
                "training",
                "session",
                "total",
            ]
        ):
            continue
        # Extract the first column — skill name is text before first number
        # Lines look like: "backstab            123    85%     10"
        parts = line.split()
        if not parts:
            continue
        # Collect leading non-numeric words as the skill name
        name_parts = []
        for part in parts:
            # Stop at first purely numeric token or percentage
            stripped = part.rstrip("%")
            if stripped.isdigit():
                break
            name_parts.append(part)
        if name_parts:
            skill_name = " ".join(name_parts).lower()
            skills.add(skill_name)

    return skills


class LearnedSkillsProvider:
    """Fetches and stores learned skills from the MUD server.

    Usage:
        provider = LearnedSkillsProvider(agent)
        await provider.fetch()
        if "backstab" in provider.skills:
            ...
    """

    def __init__(self, agent):
        self.agent = agent
        self.skills: set[str] = set()

    async def fetch(self) -> set[str]:
        """Send the 'learned' command and parse the response.

        Returns:
            The set of learned skill names (lowercase).
        """
        try:
            response = await self.agent.command_processor.process_command(
                "learned"
            )
            self.skills = parse_learned_output(response)
            logger.info(
                "Loaded %d learned skills from server", len(self.skills)
            )
        except Exception as e:
            logger.error(
                "Failed to fetch learned skills: %s", e, exc_info=True
            )
        return self.skills
