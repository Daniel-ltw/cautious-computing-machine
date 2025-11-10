"""
Container widgets for the MUD agent.

This module contains container widgets that hold other widgets.
"""

import asyncio
import logging

from rich.console import Console
from textual.containers import Container, Horizontal, ScrollableContainer

from .mapper_container import MapperContainer

from .base import (
    FULL_THRESHOLD,
    HUNGRY_THRESHOLD,
    ONE_HUNDRED_PERCENT,
    SATIATED_THRESHOLD,
    ZERO,
)
from .character_widgets import CharacterHeaderWidget
from .needs_widgets import HungerWidget, ThirstWidget
from .room_widgets import RoomWidget
from .stats_static_widgets import (
    ConStaticWidget,
    DexStaticWidget,
    DRStaticWidget,
    HRStaticWidget,
    IntStaticWidget,
    LuckStaticWidget,
    StrStaticWidget,
    WisStaticWidget,
)
from .status_widgets import StatusEffectsWidget
from .vitals_static_widgets import HPStaticWidget, MPStaticWidget, MVStaticWidget
from .worth_widgets import BankWidget, GoldWidget, QPWidget, TPWidget, XPWidget

logger = logging.getLogger(__name__)
console = Console()


class VitalsContainer(Container):
    """Container for vitals widgets and needs widgets."""

    DEFAULT_CSS = """
    VitalsContainer {
        layout: horizontal;
        height: 1;
        width: 100%;
        margin: 0;
        padding: 0;
        background: transparent;
        border: none;
    }

    Horizontal {
        width: 100%;
        height: 1;
        padding: 0;
        margin: 0;
        border: none;
        background: transparent;
    }

    #hp-widget, #mp-widget, #mv-widget, #hunger-widget, #thirst-widget {
        width: 1fr;
        height: 1;
        margin: 0 1;
    }
    """

    def __init__(self, *args, **kwargs):
        """Initialize the container."""
        super().__init__(*args, **kwargs)
        self.hp_widget = None
        self.mp_widget = None
        self.mv_widget = None
        self.hunger_widget = None
        self.thirst_widget = None

    def on_mount(self):
        """Called when the widget is mounted."""
        logger.info("VitalsContainer mounted")
        # Log the parent widget to see where we're mounted
        if hasattr(self, "parent") and self.parent:
            logger.info(f"VitalsContainer parent: {self.parent}")
        else:
            logger.warning("VitalsContainer has no parent")

        # Log our ID and CSS classes
        logger.info(f"VitalsContainer ID: {self.id}")
        logger.info(f"VitalsContainer CSS classes: {self.classes}")

        # Ensure the widget is visible
        self.styles.display = "block"
        self.styles.visibility = "visible"
        self.styles.opacity = 1.0
        logger.info(
            f"VitalsContainer display: {self.styles.display}, visibility: {self.styles.visibility}, opacity: {self.styles.opacity}"
        )

        # Removed excessive refresh call to prevent UI duplication
        logger.info("VitalsContainer mounted successfully")

        # Ensure the child widgets are initialized
        if self.hp_widget is None:
            try:
                self.hp_widget = self.query_one("#hp-widget")
                logger.info("Found hp widget via query in on_mount")

                # Ensure the widget is visible
                self.hp_widget.styles.display = "block"
                self.hp_widget.styles.visibility = "visible"
                self.hp_widget.styles.opacity = 1.0
                logger.info(
                    f"HP widget display: {self.hp_widget.styles.display}, visibility: {self.hp_widget.styles.visibility}, opacity: {self.hp_widget.styles.opacity}"
                )

                # Initialize widget without setting default values
                # Let the widget get its values from the state manager
                if hasattr(self.hp_widget, "update_display"):
                    self.hp_widget.update_display()
                    logger.info("Initialized HP static widget")
                elif hasattr(self.hp_widget, "update_progress"):
                    self.hp_widget.update_progress()
                    logger.info("Initialized HP progress widget")
                elif (
                    hasattr(self.hp_widget, "hp_current_widget")
                    and self.hp_widget.hp_current_widget
                ):
                    # It's the old widget - just update content without setting values
                    self.hp_widget.hp_current_widget.update_content()
                    logger.info("Initialized HP current widget")

                    if (
                        hasattr(self.hp_widget, "hp_max_widget")
                        and self.hp_widget.hp_max_widget
                    ):
                        self.hp_widget.hp_max_widget.update_content()
                        logger.info("Initialized HP max widget")
            except Exception as e:
                logger.error(
                    f"Failed to find hp widget in on_mount: {e}", exc_info=True
                )

        if self.mp_widget is None:
            try:
                self.mp_widget = self.query_one("#mp-widget")
                logger.info("Found mp widget via query in on_mount")

                # Ensure the widget is visible
                self.mp_widget.styles.display = "block"
                self.mp_widget.styles.visibility = "visible"
                self.mp_widget.styles.opacity = 1.0
                logger.info(
                    f"MP widget display: {self.mp_widget.styles.display}, visibility: {self.mp_widget.styles.visibility}, opacity: {self.mp_widget.styles.opacity}"
                )

                # Initialize widget without setting default values
                # Let the widget get its values from the state manager
                if hasattr(self.mp_widget, "update_display"):
                    self.mp_widget.update_display()
                    logger.info("Initialized MP static widget")
                elif hasattr(self.mp_widget, "update_progress"):
                    self.mp_widget.update_progress()
                    logger.info("Initialized MP progress widget")
                elif (
                    hasattr(self.mp_widget, "mp_current_widget")
                    and self.mp_widget.mp_current_widget
                ):
                    # It's the old widget - just update content without setting values
                    self.mp_widget.mp_current_widget.update_content()
                    logger.info("Initialized MP current widget")

                    if (
                        hasattr(self.mp_widget, "mp_max_widget")
                        and self.mp_widget.mp_max_widget
                    ):
                        self.mp_widget.mp_max_widget.update_content()
                        logger.info("Initialized MP max widget")
            except Exception as e:
                logger.error(
                    f"Failed to find mp widget in on_mount: {e}", exc_info=True
                )

        if self.mv_widget is None:
            try:
                self.mv_widget = self.query_one("#mv-widget")
                logger.info("Found mv widget via query in on_mount")

                # Ensure the widget is visible
                self.mv_widget.styles.display = "block"
                self.mv_widget.styles.visibility = "visible"
                self.mv_widget.styles.opacity = 1.0
                logger.info(
                    f"MV widget display: {self.mv_widget.styles.display}, visibility: {self.mv_widget.styles.visibility}, opacity: {self.mv_widget.styles.opacity}"
                )

                # Initialize widget without setting default values
                # Let the widget get its values from the state manager
                if hasattr(self.mv_widget, "update_display"):
                    self.mv_widget.update_display()
                    logger.info("Initialized MV static widget")
                elif hasattr(self.mv_widget, "update_progress"):
                    self.mv_widget.update_progress()
                    logger.info("Initialized MV progress widget")
                elif (
                    hasattr(self.mv_widget, "mv_current_widget")
                    and self.mv_widget.mv_current_widget
                ):
                    # It's the old widget - just update content without setting values
                    self.mv_widget.mv_current_widget.update_content()
                    logger.info("Initialized MV current widget")

                    if (
                        hasattr(self.mv_widget, "mv_max_widget")
                        and self.mv_widget.mv_max_widget
                    ):
                        self.mv_widget.mv_max_widget.update_content()
                        logger.info("Initialized MV max widget")
            except Exception as e:
                logger.error(
                    f"Failed to find mv widget in on_mount: {e}", exc_info=True
                )

    def compose(self):
        """Compose the container layout."""
        with Horizontal():
            # Use the static widgets instead of the progress widgets
            self.hp_widget = yield HPStaticWidget(id="hp-widget")
            self.mp_widget = yield MPStaticWidget(id="mp-widget")
            self.mv_widget = yield MVStaticWidget(id="mv-widget")
            self.hunger_widget = yield HungerWidget(id="hunger-widget")
            self.thirst_widget = yield ThirstWidget(id="thirst-widget")


class NeedsContainer(Container):
    """Container for needs widgets."""

    DEFAULT_CSS = """
    NeedsContainer {
        layout: horizontal;
        height: 1;
        width: 100%;
        margin: 0;
        padding: 0;
        background: transparent;
        border: none;
    }

    Horizontal {
        width: 100%;
        height: 1;
        padding: 0;
        margin: 0;
        border: none;
        background: transparent;
    }

    #hunger-widget, #thirst-widget {
        width: 1fr;
        height: 1;
        margin: 0 1;
    }
    """

    def __init__(self, *args, **kwargs):
        """Initialize the container."""
        super().__init__(*args, **kwargs)
        self.hunger_widget = None
        self.thirst_widget = None

    def compose(self):
        """Compose the container layout."""
        with Horizontal():
            self.hunger_widget = yield HungerWidget(id="hunger-widget")
            self.thirst_widget = yield ThirstWidget(id="thirst-widget")


class StatsContainer(Container):
    """Container for stats widgets."""

    DEFAULT_CSS = """
    StatsContainer {
        layout: grid;
        grid-size: 4 2;
        grid-columns: 1fr 1fr 1fr 1fr;
        grid-rows: 1fr 1fr;
        height: 3;
        width: 100%;
        margin: 0;
        padding: 0;
        background: transparent;
        border: none;
    }

    #str-widget, #int-widget, #wis-widget, #dex-widget,
    #con-widget, #luck-widget, #hr-widget, #dr-widget {
        width: 1fr;
        height: 1;
        margin: 0;
        padding: 0;
    }
    """

    def __init__(self, *args, **kwargs):
        """Initialize the container."""
        super().__init__(*args, **kwargs)
        self.str_widget = None
        self.int_widget = None
        self.wis_widget = None
        self.dex_widget = None
        self.con_widget = None
        self.luck_widget = None
        self.hr_widget = None
        self.dr_widget = None

    def on_mount(self):
        """Called when the widget is mounted."""
        logger.info("StatsContainer mounted")
        # Log the parent widget to see where we're mounted
        if hasattr(self, "parent") and self.parent:
            logger.info(f"StatsContainer parent: {self.parent}")
        else:
            logger.warning("StatsContainer has no parent")

        # Log our ID and CSS classes
        logger.info(f"StatsContainer ID: {self.id}")
        logger.info(f"StatsContainer CSS classes: {self.classes}")

        # Removed excessive refresh call to prevent UI duplication
        logger.info("StatsContainer mounted successfully")

    def compose(self):
        """Compose the container layout."""
        # First row
        self.str_widget = yield StrStaticWidget(id="str-widget")
        self.int_widget = yield IntStaticWidget(id="int-widget")
        self.wis_widget = yield WisStaticWidget(id="wis-widget")
        self.dex_widget = yield DexStaticWidget(id="dex-widget")

        # Second row
        self.con_widget = yield ConStaticWidget(id="con-widget")
        self.luck_widget = yield LuckStaticWidget(id="luck-widget")
        self.hr_widget = yield HRStaticWidget(id="hr-widget")
        self.dr_widget = yield DRStaticWidget(id="dr-widget")


class WorthContainer(Container):
    """Container for worth widgets."""

    DEFAULT_CSS = """
    WorthContainer {
        layout: horizontal;
        height: 1;
        width: 100%;
        margin: 0;
        padding: 0;
        background: transparent;
        border: none;
    }

    Horizontal {
        width: 100%;
        height: 1;
        padding: 0;
        margin: 0;
        border: none;
        background: transparent;
    }

    #gold-widget, #bank-widget, #qp-widget, #tp-widget, #xp-widget {
        width: 1fr;
        height: 1;
        margin: 0 1;
    }
    """

    def __init__(self, *args, **kwargs):
        """Initialize the container."""
        super().__init__(*args, **kwargs)
        self.gold_widget = None
        self.bank_widget = None
        self.qp_widget = None
        self.tp_widget = None
        self.xp_widget = None

    def compose(self):
        """Compose the container layout."""
        with Horizontal():
            self.gold_widget = yield GoldWidget(id="gold-widget")
            self.bank_widget = yield BankWidget(id="bank-widget")
            self.qp_widget = yield QPWidget(id="qp-widget")
            self.tp_widget = yield TPWidget(id="tp-widget")
            self.xp_widget = yield XPWidget(id="xp-widget")


class StatusContainer(Container):
    """Container widget that holds all the status widgets."""

    DEFAULT_CSS = """
    StatusContainer {
        layout: vertical;
        width: 100%;
        height: 100%;
        margin: 0;
        padding: 0;
        background: transparent;
        border: none;
    }

    #character-header {
        width: 100%;
        height: 1;
        margin-bottom: 1;
    }

    #vitals-container {
        width: 100%;
        height: 1;
        margin-bottom: 1;
    }

    /* Needs container removed - hunger and thirst now in vitals container */

    #worth-container {
        width: 100%;
        height: 1;
        margin-bottom: 1;
    }

    #stats-container {
        width: 100%;
        height: 3;
        margin-bottom: 1;
    }

    #status-effects-widget {
        width: 100%;
        height: 1;
    }
    """

    def __init__(self, *args, **kwargs):
        """Initialize the container."""
        super().__init__(*args, **kwargs)
        self.character_header = None
        self.vitals_container = None
        self.needs_container = None
        self.worth_container = None
        self.stats_container = None
        self.status_effects = None

    def on_mount(self):
        """Called when the widget is mounted."""
        logger.info("StatusContainer mounted")
        # Log the parent widget to see where we're mounted
        if hasattr(self, "parent") and self.parent:
            logger.info(f"StatusContainer parent: {self.parent}")
        else:
            logger.warning("StatusContainer has no parent")

        # Log our ID and CSS classes
        logger.info(f"StatusContainer ID: {self.id}")
        logger.info(f"StatusContainer CSS classes: {self.classes}")

        # Removed excessive refresh call to prevent UI duplication
        logger.info("StatusContainer mounted successfully")

    def compose(self):
        """Compose the container layout."""
        # First row: Character header - create an instance directly
        self.character_header = CharacterHeaderWidget(id="character-header")
        yield self.character_header

        # Second row: Vitals (now includes hunger and thirst)
        self.vitals_container = VitalsContainer(id="vitals-container")
        yield self.vitals_container

        # Third row: Worth
        self.worth_container = WorthContainer(id="worth-container")
        yield self.worth_container

        # Fourth row: Stats
        self.stats_container = StatsContainer(id="stats-container")
        yield self.stats_container

        # Fifth row: Status effects
        self.status_effects = StatusEffectsWidget(id="status-effects-widget")
        yield self.status_effects

    async def _deferred_update(self, state_manager):
        """Deferred update that waits before retrying."""
        import asyncio
        await asyncio.sleep(0.1)  # Wait 100ms before retrying
        await self.update_from_state_manager(state_manager)

    async def update_from_state_manager(self, state_manager):
        """Update all widgets from the state manager's state.

        Args:
            state_manager: The state manager containing the state
        """
        try:
            # Update character header
            if state_manager is None:
                logger.warning("State manager is None, cannot update character header")
                return

            # Check if the container is mounted
            if not self.is_mounted:
                logger.debug("StatusContainer not mounted yet, deferring update")
                # Schedule another update after a short delay using asyncio to avoid blocking
                import asyncio
                asyncio.create_task(self._deferred_update(state_manager))
                return

            # Log the state manager's character data for debugging
            logger.info(
                f"State manager character data: name={state_manager.character_name}, level={state_manager.level}, class={state_manager.character_class}"
            )
            logger.info(
                f"State manager vitals: HP={state_manager.health.get('current', 'N/A')}/{state_manager.health.get('max', 'N/A')}, MP={state_manager.mana.get('current', 'N/A')}/{state_manager.mana.get('max', 'N/A')}, MV={state_manager.movement.get('current', 'N/A')}/{state_manager.movement.get('max', 'N/A')}"
            )
            logger.info(f"State manager status effects: {state_manager.status_effects}")

            # Check if character_header is None
            if self.character_header is None:
                logger.warning(
                    "Character header is None, cannot update character attributes"
                )
                # Try to find the character header widget
                try:
                    self.character_header = self.query_one("#character-header")
                    logger.info("Found character header widget via query")
                except Exception as e:
                    logger.error(
                        f"Failed to find character header widget: {e}", exc_info=True
                    )
                    return

            # Update character header
            self.character_header.character_name = state_manager.character_name
            self.character_header.level = state_manager.level
            self.character_header.race = state_manager.race
            self.character_header.character_class = state_manager.character_class
            self.character_header.update_content()

            # Update vitals
            if self.vitals_container:
                # Update HP widget
                if (
                    hasattr(self.vitals_container, "hp_widget")
                    and self.vitals_container.hp_widget
                ):
                    # Check if it's a static or progress widget
                    if hasattr(
                        self.vitals_container.hp_widget, "current_value"
                    ) and hasattr(self.vitals_container.hp_widget, "max_value"):
                        # It's a static or progress widget
                        self.vitals_container.hp_widget.current_value = (
                            state_manager.hp_current
                        )
                        self.vitals_container.hp_widget.max_value = state_manager.hp_max

                        # Check if it has update_display (static) or update_progress (progress)
                        if hasattr(self.vitals_container.hp_widget, "update_display"):
                            self.vitals_container.hp_widget.update_display()
                        elif hasattr(
                            self.vitals_container.hp_widget, "update_progress"
                        ):
                            self.vitals_container.hp_widget.update_progress()
                            logger.info(
                                f"Updated HP progress widget with current={state_manager.hp_current}, max={state_manager.hp_max}"
                            )
                    elif (
                        hasattr(self.vitals_container.hp_widget, "hp_current_widget")
                        and self.vitals_container.hp_widget.hp_current_widget
                    ):
                        # It's the old widget
                        self.vitals_container.hp_widget.hp_current_widget.value = (
                            state_manager.hp_current
                        )
                        self.vitals_container.hp_widget.hp_current_widget.in_combat = (
                            state_manager.in_combat
                        )
                        self.vitals_container.hp_widget.hp_current_widget.update_content()

                        if (
                            hasattr(self.vitals_container.hp_widget, "hp_max_widget")
                            and self.vitals_container.hp_widget.hp_max_widget
                        ):
                            self.vitals_container.hp_widget.hp_max_widget.value = (
                                state_manager.hp_max
                            )
                            self.vitals_container.hp_widget.hp_max_widget.update_content()

                        logger.info(
                            f"Updated HP widget with current={state_manager.hp_current}, max={state_manager.hp_max}"
                        )

                # Update MP widget
                if (
                    hasattr(self.vitals_container, "mp_widget")
                    and self.vitals_container.mp_widget
                ):
                    # Check if it's a static or progress widget
                    if hasattr(
                        self.vitals_container.mp_widget, "current_value"
                    ) and hasattr(self.vitals_container.mp_widget, "max_value"):
                        # It's a static or progress widget
                        self.vitals_container.mp_widget.current_value = (
                            state_manager.mp_current
                        )
                        self.vitals_container.mp_widget.max_value = state_manager.mp_max

                        # Check if it has update_display (static) or update_progress (progress)
                        if hasattr(self.vitals_container.mp_widget, "update_display"):
                            self.vitals_container.mp_widget.update_display()
                        elif hasattr(
                            self.vitals_container.mp_widget, "update_progress"
                        ):
                            self.vitals_container.mp_widget.update_progress()
                            logger.info(
                                f"Updated MP progress widget with current={state_manager.mp_current}, max={state_manager.mp_max}"
                            )
                    elif (
                        hasattr(self.vitals_container.mp_widget, "mp_current_widget")
                        and self.vitals_container.mp_widget.mp_current_widget
                    ):
                        # It's the old widget
                        self.vitals_container.mp_widget.mp_current_widget.value = (
                            state_manager.mp_current
                        )
                        self.vitals_container.mp_widget.mp_current_widget.in_combat = (
                            state_manager.in_combat
                        )
                        self.vitals_container.mp_widget.mp_current_widget.update_content()

                        if (
                            hasattr(self.vitals_container.mp_widget, "mp_max_widget")
                            and self.vitals_container.mp_widget.mp_max_widget
                        ):
                            self.vitals_container.mp_widget.mp_max_widget.value = (
                                state_manager.mp_max
                            )
                            self.vitals_container.mp_widget.mp_max_widget.update_content()

                        logger.info(
                            f"Updated MP widget with current={state_manager.mp_current}, max={state_manager.mp_max}"
                        )

                # Update MV widget
                if (
                    hasattr(self.vitals_container, "mv_widget")
                    and self.vitals_container.mv_widget
                ):
                    # Check if it's a static or progress widget
                    if hasattr(
                        self.vitals_container.mv_widget, "current_value"
                    ) and hasattr(self.vitals_container.mv_widget, "max_value"):
                        # It's a static or progress widget
                        self.vitals_container.mv_widget.current_value = (
                            state_manager.mv_current
                        )
                        self.vitals_container.mv_widget.max_value = state_manager.mv_max

                        # Check if it has update_display (static) or update_progress (progress)
                        if hasattr(self.vitals_container.mv_widget, "update_display"):
                            self.vitals_container.mv_widget.update_display()
                        elif hasattr(
                            self.vitals_container.mv_widget, "update_progress"
                        ):
                            self.vitals_container.mv_widget.update_progress()
                            logger.info(
                                f"Updated MV progress widget with current={state_manager.mv_current}, max={state_manager.mv_max}"
                            )
                    elif (
                        hasattr(self.vitals_container.mv_widget, "mv_current_widget")
                        and self.vitals_container.mv_widget.mv_current_widget
                    ):
                        # It's the old widget
                        self.vitals_container.mv_widget.mv_current_widget.value = (
                            state_manager.mv_current
                        )
                        self.vitals_container.mv_widget.mv_current_widget.in_combat = (
                            state_manager.in_combat
                        )
                        self.vitals_container.mv_widget.mv_current_widget.update_content()

                        if (
                            hasattr(self.vitals_container.mv_widget, "mv_max_widget")
                            and self.vitals_container.mv_widget.mv_max_widget
                        ):
                            self.vitals_container.mv_widget.mv_max_widget.value = (
                                state_manager.mv_max
                            )
                            self.vitals_container.mv_widget.mv_max_widget.update_content()

                        logger.info(
                            f"Updated MV widget with current={state_manager.mv_current}, max={state_manager.mv_max}"
                        )

            # Try to update from GMCP data directly
            if (
                hasattr(state_manager, "agent")
                and state_manager.agent is not None
                and hasattr(state_manager.agent, "aardwolf_gmcp")
            ):
                # Force an update from GMCP
                updates = state_manager.agent.aardwolf_gmcp.update_from_gmcp()
                if updates:
                    logger.info(f"Forced GMCP update: {updates}")

                # Directly update all widgets with state manager data
                await self.update_all_widgets_directly(state_manager)

            # Always force a direct update of the vitals widgets
            if (
                self.vitals_container
                and self.vitals_container.hp_widget
                and self.vitals_container.mp_widget
                and self.vitals_container.mv_widget
            ):
                # Force update HP widget
                if hasattr(
                    self.vitals_container.hp_widget, "current_value"
                ) and hasattr(self.vitals_container.hp_widget, "max_value"):
                    # It's a static or progress widget
                    self.vitals_container.hp_widget.current_value = (
                        state_manager.hp_current
                    )
                    self.vitals_container.hp_widget.max_value = state_manager.hp_max

                    # Check if it has update_display (static) or update_progress (progress)
                    if hasattr(self.vitals_container.hp_widget, "update_display"):
                        self.vitals_container.hp_widget.update_display()
                    elif hasattr(self.vitals_container.hp_widget, "update_progress"):
                        self.vitals_container.hp_widget.update_progress()
                elif (
                    hasattr(self.vitals_container.hp_widget, "hp_current_widget")
                    and self.vitals_container.hp_widget.hp_current_widget
                ):
                    # It's the old widget
                    self.vitals_container.hp_widget.hp_current_widget.value = (
                        state_manager.hp_current
                    )
                    self.vitals_container.hp_widget.hp_current_widget.update_content()

                    if (
                        hasattr(self.vitals_container.hp_widget, "hp_max_widget")
                        and self.vitals_container.hp_widget.hp_max_widget
                    ):
                        self.vitals_container.hp_widget.hp_max_widget.value = (
                            state_manager.hp_max
                        )
                        self.vitals_container.hp_widget.hp_max_widget.update_content()

                # Force update MP widget
                if hasattr(
                    self.vitals_container.mp_widget, "current_value"
                ) and hasattr(self.vitals_container.mp_widget, "max_value"):
                    # It's a static or progress widget
                    self.vitals_container.mp_widget.current_value = (
                        state_manager.mp_current
                    )
                    self.vitals_container.mp_widget.max_value = state_manager.mp_max

                    # Check if it has update_display (static) or update_progress (progress)
                    if hasattr(self.vitals_container.mp_widget, "update_display"):
                        self.vitals_container.mp_widget.update_display()
                    elif hasattr(self.vitals_container.mp_widget, "update_progress"):
                        self.vitals_container.mp_widget.update_progress()
                elif (
                    hasattr(self.vitals_container.mp_widget, "mp_current_widget")
                    and self.vitals_container.mp_widget.mp_current_widget
                ):
                    # It's the old widget
                    self.vitals_container.mp_widget.mp_current_widget.value = (
                        state_manager.mp_current
                    )
                    self.vitals_container.mp_widget.mp_current_widget.update_content()

                    if (
                        hasattr(self.vitals_container.mp_widget, "mp_max_widget")
                        and self.vitals_container.mp_widget.mp_max_widget
                    ):
                        self.vitals_container.mp_widget.mp_max_widget.value = (
                            state_manager.mp_max
                        )
                        self.vitals_container.mp_widget.mp_max_widget.update_content()

                # Force update MV widget
                if hasattr(
                    self.vitals_container.mv_widget, "current_value"
                ) and hasattr(self.vitals_container.mv_widget, "max_value"):
                    # It's a static or progress widget
                    self.vitals_container.mv_widget.current_value = (
                        state_manager.mv_current
                    )
                    self.vitals_container.mv_widget.max_value = state_manager.mv_max

                    # Check if it has update_display (static) or update_progress (progress)
                    if hasattr(self.vitals_container.mv_widget, "update_display"):
                        self.vitals_container.mv_widget.update_display()
                    elif hasattr(self.vitals_container.mv_widget, "update_progress"):
                        self.vitals_container.mv_widget.update_progress()
                elif (
                    hasattr(self.vitals_container.mv_widget, "mv_current_widget")
                    and self.vitals_container.mv_widget.mv_current_widget
                ):
                    # It's the old widget
                    self.vitals_container.mv_widget.mv_current_widget.value = (
                        state_manager.mv_current
                    )
                    self.vitals_container.mv_widget.mv_current_widget.update_content()

                    if (
                        hasattr(self.vitals_container.mv_widget, "mv_max_widget")
                        and self.vitals_container.mv_widget.mv_max_widget
                    ):
                        self.vitals_container.mv_widget.mv_max_widget.value = (
                            state_manager.mv_max
                        )
                        self.vitals_container.mv_widget.mv_max_widget.update_content()

            # Always force a direct update of the needs widgets
            if hasattr(self, "needs_container") and self.needs_container:
                # Force update hunger widget
                if (
                    hasattr(self.needs_container, "hunger_widget")
                    and self.needs_container.hunger_widget
                ):
                    hunger_text = "Unknown"
                    if hasattr(state_manager, "_get_hunger_text") and hasattr(
                        state_manager, "hunger"
                    ):
                        hunger_text = state_manager._get_hunger_text(
                            state_manager.hunger["current"]
                        )
                    self.needs_container.hunger_widget.current = state_manager.hunger[
                        "current"
                    ]
                    self.needs_container.hunger_widget.maximum = state_manager.hunger[
                        "max"
                    ]
                    self.needs_container.hunger_widget.text = hunger_text
                    self.needs_container.hunger_widget.update_content()

                # Force update thirst widget
                if (
                    hasattr(self.needs_container, "thirst_widget")
                    and self.needs_container.thirst_widget
                ):
                    thirst_text = "Unknown"
                    if hasattr(state_manager, "_get_thirst_text") and hasattr(
                        state_manager, "thirst"
                    ):
                        thirst_text = state_manager._get_thirst_text(
                            state_manager.thirst["current"]
                        )
                    self.needs_container.thirst_widget.current = state_manager.thirst[
                        "current"
                    ]
                    self.needs_container.thirst_widget.maximum = state_manager.thirst[
                        "max"
                    ]
                    self.needs_container.thirst_widget.text = thirst_text
                    self.needs_container.thirst_widget.update_content()

            # Check if character_header is mounted
            if (
                not hasattr(self.character_header, "is_mounted")
                or not self.character_header.is_mounted
            ):
                logger.debug("Character header not mounted yet, deferring update")
                # Schedule another update after a short delay using asyncio to avoid blocking
                import asyncio
                asyncio.create_task(self._deferred_update(state_manager))
                return

            # Check if character_name exists and is not None
            if (
                hasattr(state_manager, "character_name")
                and state_manager.character_name is not None
            ):
                self.character_header.character_name = state_manager.character_name
            else:
                self.character_header.character_name = "Unknown"

            # Check if level exists
            if hasattr(state_manager, "level") and state_manager.level is not None:
                self.character_header.level = (
                    str(state_manager.level) if state_manager.level > 0 else "Unknown"
                )
            else:
                self.character_header.level = "Unknown"

            # Check if alignment exists and is not None
            if (
                hasattr(state_manager, "alignment")
                and state_manager.alignment is not None
            ):
                self.character_header.alignment = state_manager.alignment
            else:
                self.character_header.alignment = "Unknown"

            # Check for other character attributes
            if hasattr(state_manager, "race") and state_manager.race is not None:
                self.character_header.race = state_manager.race
            if (
                hasattr(state_manager, "character_class")
                and state_manager.character_class is not None
            ):
                self.character_header.character_class = state_manager.character_class
            if (
                hasattr(state_manager, "subclass")
                and state_manager.subclass is not None
            ):
                self.character_header.subclass = state_manager.subclass
            if hasattr(state_manager, "clan") and state_manager.clan is not None:
                self.character_header.clan = state_manager.clan
            if hasattr(state_manager, "remorts") and state_manager.remorts is not None:
                self.character_header.remorts = state_manager.remorts
            if hasattr(state_manager, "tier") and state_manager.tier is not None:
                self.character_header.tier = state_manager.tier

            # Update vitals
            try:
                # Check if vitals_container is None
                if self.vitals_container is None:
                    logger.warning("Vitals container is None, cannot update vitals")
                    # Try to find the vitals container
                    try:
                        self.vitals_container = self.query_one("#vitals-container")
                        logger.info("Found vitals container via query")
                    except Exception as e:
                        logger.error(
                            f"Failed to find vitals container: {e}", exc_info=True
                        )
                        return

                # Check if vitals_container is mounted
                if (
                    not hasattr(self.vitals_container, "is_mounted")
                    or not self.vitals_container.is_mounted
                ):
                    logger.debug("Vitals container not mounted yet, deferring update")
                    # Schedule another update after a short delay using asyncio to avoid blocking
                    import asyncio
                    asyncio.create_task(self._deferred_update(state_manager))
                    return

                # First try to get vitals from GMCP
                if (
                    hasattr(state_manager, "agent")
                    and state_manager.agent is not None
                    and hasattr(state_manager.agent, "aardwolf_gmcp")
                ):
                    gmcp = state_manager.agent.aardwolf_gmcp
                    # Force an update from GMCP to get the latest data
                    gmcp.update_from_gmcp()
                    # Get the vitals data
                    vitals_data = gmcp.get_vitals_data()
                    logger.info(f"Got vitals data from GMCP: {vitals_data}")

                    # Add detailed logging for debugging
                    logger.info(f"Raw GMCP char_data keys: {list(gmcp.char_data.keys()) if gmcp.char_data else 'No char_data'}")
                    if gmcp.char_data and 'vitals' in gmcp.char_data:
                        logger.info(f"Raw vitals data: {gmcp.char_data['vitals']}")
                    else:
                        logger.warning("No vitals data found in GMCP char_data")

                    # Check if the child widgets are initialized
                    if self.vitals_container.hp_widget is None:
                        try:
                            self.vitals_container.hp_widget = (
                                self.vitals_container.query_one("#hp-widget")
                            )
                            logger.info("Found hp widget via query")
                        except Exception as e:
                            logger.error(
                                f"Failed to find hp widget: {e}", exc_info=True
                            )
                            return

                    if self.vitals_container.mp_widget is None:
                        try:
                            self.vitals_container.mp_widget = (
                                self.vitals_container.query_one("#mp-widget")
                            )
                            logger.info("Found mp widget via query")
                        except Exception as e:
                            logger.error(
                                f"Failed to find mp widget: {e}", exc_info=True
                            )
                            return

                    if self.vitals_container.mv_widget is None:
                        try:
                            self.vitals_container.mv_widget = (
                                self.vitals_container.query_one("#mv-widget")
                            )
                            logger.info("Found mv widget via query")
                        except Exception as e:
                            logger.error(
                                f"Failed to find mv widget: {e}", exc_info=True
                            )
                            return

                    # Check for hunger and thirst widgets in vitals container
                    if self.vitals_container.hunger_widget is None:
                        try:
                            self.vitals_container.hunger_widget = (
                                self.vitals_container.query_one("#hunger-widget")
                            )
                            logger.info(
                                "Found hunger widget via query in vitals container"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to find hunger widget in vitals container: {e}",
                                exc_info=True,
                            )
                            return

                    if self.vitals_container.thirst_widget is None:
                        try:
                            self.vitals_container.thirst_widget = (
                                self.vitals_container.query_one("#thirst-widget")
                            )
                            logger.info(
                                "Found thirst widget via query in vitals container"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to find thirst widget in vitals container: {e}",
                                exc_info=True,
                            )
                            return

                    if vitals_data:
                        # Update from GMCP vitals data
                        # The vitals widgets will handle the updates through their event listeners
                        # We just need to emit the events with the right data

                        # Create a vitals update event with the nested structure expected by widgets
                        vitals_update = {
                            "hp": {
                                "current": vitals_data.get("hp", 0),
                                "max": vitals_data.get("maxhp", 0),
                            },
                            "mp": {
                                "current": vitals_data.get("mana", 0),
                                "max": vitals_data.get("maxmana", 0),
                            },
                            "mv": {
                                "current": vitals_data.get("moves", 0),
                                "max": vitals_data.get("maxmoves", 0),
                            },
                        }

                        # Log the vitals update for debugging
                        logger.info(
                            f"Created vitals update from GMCP data: {vitals_update}"
                        )

                        # Also directly update the widgets for immediate feedback
                        try:
                            # Update HP widget
                            if (
                                self.vitals_container.hp_widget
                                and hasattr(
                                    self.vitals_container.hp_widget, "hp_current_widget"
                                )
                                and self.vitals_container.hp_widget.hp_current_widget
                                is not None
                            ):
                                self.vitals_container.hp_widget.hp_current_widget.value = vitals_data.get(
                                    "hp", 0
                                )
                                self.vitals_container.hp_widget.hp_current_widget.update_content()
                                logger.info(
                                    f"Directly updated HP current widget with value: {vitals_data.get('hp', 0)}"
                                )
                            else:
                                logger.warning(
                                    "HP current widget not available for direct update"
                                )

                            if (
                                self.vitals_container.hp_widget
                                and hasattr(
                                    self.vitals_container.hp_widget, "hp_max_widget"
                                )
                                and self.vitals_container.hp_widget.hp_max_widget
                                is not None
                            ):
                                self.vitals_container.hp_widget.hp_max_widget.value = (
                                    vitals_data.get("maxhp", 0)
                                )
                                self.vitals_container.hp_widget.hp_max_widget.update_content()
                                logger.info(
                                    f"Directly updated HP max widget with value: {vitals_data.get('maxhp', 0)}"
                                )
                            else:
                                logger.warning(
                                    "HP max widget not available for direct update"
                                )

                            # Update MP widget
                            if (
                                self.vitals_container.mp_widget
                                and hasattr(
                                    self.vitals_container.mp_widget, "mp_current_widget"
                                )
                                and self.vitals_container.mp_widget.mp_current_widget
                                is not None
                            ):
                                self.vitals_container.mp_widget.mp_current_widget.value = vitals_data.get(
                                    "mana", 0
                                )
                                self.vitals_container.mp_widget.mp_current_widget.update_content()
                                logger.info(
                                    f"Directly updated MP current widget with value: {vitals_data.get('mana', 0)}"
                                )
                            else:
                                logger.warning(
                                    "MP current widget not available for direct update"
                                )

                            if (
                                self.vitals_container.mp_widget
                                and hasattr(
                                    self.vitals_container.mp_widget, "mp_max_widget"
                                )
                                and self.vitals_container.mp_widget.mp_max_widget
                                is not None
                            ):
                                self.vitals_container.mp_widget.mp_max_widget.value = (
                                    vitals_data.get("maxmana", 0)
                                )
                                self.vitals_container.mp_widget.mp_max_widget.update_content()
                                logger.info(
                                    f"Directly updated MP max widget with value: {vitals_data.get('maxmana', 0)}"
                                )
                            else:
                                logger.warning(
                                    "MP max widget not available for direct update"
                                )

                            # Update MV widget
                            if (
                                self.vitals_container.mv_widget
                                and hasattr(
                                    self.vitals_container.mv_widget, "mv_current_widget"
                                )
                                and self.vitals_container.mv_widget.mv_current_widget
                                is not None
                            ):
                                self.vitals_container.mv_widget.mv_current_widget.value = vitals_data.get(
                                    "moves", 0
                                )
                                self.vitals_container.mv_widget.mv_current_widget.update_content()
                                logger.info(
                                    f"Directly updated MV current widget with value: {vitals_data.get('moves', 0)}"
                                )
                            else:
                                logger.warning(
                                    "MV current widget not available for direct update"
                                )

                            if (
                                self.vitals_container.mv_widget
                                and hasattr(
                                    self.vitals_container.mv_widget, "mv_max_widget"
                                )
                                and self.vitals_container.mv_widget.mv_max_widget
                                is not None
                            ):
                                self.vitals_container.mv_widget.mv_max_widget.value = (
                                    vitals_data.get("maxmoves", 0)
                                )
                                self.vitals_container.mv_widget.mv_max_widget.update_content()
                                logger.info(
                                    f"Directly updated MV max widget with value: {vitals_data.get('maxmoves', 0)}"
                                )
                            else:
                                logger.warning(
                                    "MV max widget not available for direct update"
                                )

                            # Update hunger widget in vitals container
                            if self.vitals_container.hunger_widget is not None:
                                self.vitals_container.hunger_widget.current = (
                                    state_manager.hunger["current"]
                                )
                                self.vitals_container.hunger_widget.maximum = (
                                    state_manager.hunger["max"]
                                )
                                hunger_text = "Unknown"
                                if hasattr(
                                    state_manager, "_get_hunger_text"
                                ) and hasattr(state_manager, "hunger"):
                                    hunger_text = state_manager._get_hunger_text(
                                        state_manager.hunger["current"]
                                    )
                                self.vitals_container.hunger_widget.text = hunger_text
                                self.vitals_container.hunger_widget.update_content()
                                logger.info(
                                    f"Directly updated hunger widget with value: {state_manager.hunger['current']}/{state_manager.hunger['max']} ({hunger_text})"
                                )
                            else:
                                logger.warning(
                                    "Hunger widget not available for direct update"
                                )

                            # Update thirst widget in vitals container
                            if self.vitals_container.thirst_widget is not None:
                                self.vitals_container.thirst_widget.current = (
                                    state_manager.thirst["current"]
                                )
                                self.vitals_container.thirst_widget.maximum = (
                                    state_manager.thirst["max"]
                                )
                                thirst_text = "Unknown"
                                if hasattr(
                                    state_manager, "_get_thirst_text"
                                ) and hasattr(state_manager, "thirst"):
                                    thirst_text = state_manager._get_thirst_text(
                                        state_manager.thirst["current"]
                                    )
                                self.vitals_container.thirst_widget.text = thirst_text
                                self.vitals_container.thirst_widget.update_content()
                                logger.info(
                                    f"Directly updated thirst widget with value: {state_manager.thirst['current']}/{state_manager.thirst['max']} ({thirst_text})"
                                )
                            else:
                                logger.warning(
                                    "Thirst widget not available for direct update"
                                )
                        except Exception as e:
                            logger.error(
                                f"Error directly updating vitals widgets: {e}",
                                exc_info=True,
                            )

                        # Emit the vitals update event if we have data
                        if vitals_update and hasattr(state_manager, "events"):
                            state_manager.events.emit("vitals_update", vitals_update)
                            logger.debug(
                                f"Emitted vitals_update event with data: {vitals_update}"
                            )
                    else:
                        # Fall back to state manager if GMCP data not available
                        # Create a vitals update event from state manager data
                        vitals_update = {
                            "hp": {
                                "current": state_manager.health["current"],
                                "max": state_manager.health["max"],
                            },
                            "mp": {
                                "current": state_manager.mana["current"],
                                "max": state_manager.mana["max"],
                            },
                            "mv": {
                                "current": state_manager.movement["current"],
                                "max": state_manager.movement["max"],
                            },
                        }

                        # Emit the vitals update event
                        if hasattr(state_manager, "events"):
                            state_manager.events.emit("vitals_update", vitals_update)
                            logger.debug(
                                f"Emitted vitals_update event with state manager data: {vitals_update}"
                            )
                else:
                    # Fall back to state manager if GMCP not available
                    # Create a vitals update event from state manager data
                    vitals_update = {
                        "hp": {
                            "current": state_manager.health["current"],
                            "max": state_manager.health["max"],
                        },
                        "mp": {
                            "current": state_manager.mana["current"],
                            "max": state_manager.mana["max"],
                        },
                        "mv": {
                            "current": state_manager.movement["current"],
                            "max": state_manager.movement["max"],
                        },
                    }

                    # Emit the vitals update event
                    if hasattr(state_manager, "events"):
                        state_manager.events.emit("vitals_update", vitals_update)
                        logger.debug(
                            f"Emitted vitals_update event with state manager data: {vitals_update}"
                        )
            except (KeyError, TypeError, AttributeError) as e:
                logger.error(f"Error updating vitals: {e}", exc_info=True)

            # Update hunger and thirst widgets in vitals container
            try:
                # Check if vitals_container has hunger and thirst widgets
                if (
                    hasattr(self.vitals_container, "hunger_widget")
                    and self.vitals_container.hunger_widget is not None
                ):
                    # Update hunger widget
                    self.vitals_container.hunger_widget.current = state_manager.hunger[
                        "current"
                    ]
                    self.vitals_container.hunger_widget.maximum = state_manager.hunger[
                        "max"
                    ]

                    # Calculate text representation for hunger
                    if state_manager.hunger["max"] > 0:
                        hunger_percent = int(
                            (
                                state_manager.hunger["current"]
                                / state_manager.hunger["max"]
                            )
                            * ONE_HUNDRED_PERCENT
                        )
                        self.vitals_container.hunger_widget.text = (
                            "Full"
                            if hunger_percent > FULL_THRESHOLD
                            else "Satiated"
                            if hunger_percent > SATIATED_THRESHOLD
                            else "Hungry"
                            if hunger_percent > HUNGRY_THRESHOLD
                            else "Starving"
                        )
                    self.vitals_container.hunger_widget.update_content()
                    logger.info(
                        f"Updated hunger widget in vitals container: {state_manager.hunger['current']}/{state_manager.hunger['max']}"
                    )

                if (
                    hasattr(self.vitals_container, "thirst_widget")
                    and self.vitals_container.thirst_widget is not None
                ):
                    # Update thirst widget
                    self.vitals_container.thirst_widget.current = state_manager.thirst[
                        "current"
                    ]
                    self.vitals_container.thirst_widget.maximum = state_manager.thirst[
                        "max"
                    ]

                    # Calculate text representation for thirst
                    if state_manager.thirst["max"] > 0:
                        thirst_percent = int(
                            (
                                state_manager.thirst["current"]
                                / state_manager.thirst["max"]
                            )
                            * ONE_HUNDRED_PERCENT
                        )
                        self.vitals_container.thirst_widget.text = (
                            "Quenched"
                            if thirst_percent > FULL_THRESHOLD
                            else "Not Thirsty"
                            if thirst_percent > SATIATED_THRESHOLD
                            else "Thirsty"
                            if thirst_percent > HUNGRY_THRESHOLD
                            else "Parched"
                        )
                    self.vitals_container.thirst_widget.update_content()
                    logger.info(
                        f"Updated thirst widget in vitals container: {state_manager.thirst['current']}/{state_manager.thirst['max']}"
                    )
            except (KeyError, TypeError, AttributeError, ZeroDivisionError) as e:
                logger.error(
                    f"Error updating hunger and thirst widgets: {e}", exc_info=True
                )

            # Quest info removed

            # Update worth
            try:
                # Check if worth_container is None
                if self.worth_container is None:
                    logger.warning("Worth container is None, cannot update worth")
                    # Try to find the worth container
                    try:
                        self.worth_container = self.query_one("#worth-container")
                        logger.info("Found worth container via query")
                    except Exception as e:
                        logger.error(
                            f"Failed to find worth container: {e}", exc_info=True
                        )
                        return

                # Check if worth_container is mounted
                if (
                    not hasattr(self.worth_container, "is_mounted")
                    or not self.worth_container.is_mounted
                ):
                    logger.debug("Worth container not mounted yet, deferring update")
                    # Schedule another update after a short delay using asyncio to avoid blocking
                    import asyncio
                    asyncio.create_task(self._deferred_update(state_manager))
                    return

                # Check if the child widgets are initialized
                if self.worth_container.gold_widget is None:
                    try:
                        self.worth_container.gold_widget = (
                            self.worth_container.query_one("#gold-widget")
                        )
                        logger.info("Found gold widget via query")
                    except Exception as e:
                        logger.error(f"Failed to find gold widget: {e}", exc_info=True)
                        return

                if self.worth_container.bank_widget is None:
                    try:
                        self.worth_container.bank_widget = (
                            self.worth_container.query_one("#bank-widget")
                        )
                        logger.info("Found bank widget via query")
                    except Exception as e:
                        logger.error(f"Failed to find bank widget: {e}", exc_info=True)
                        return

                if self.worth_container.qp_widget is None:
                    try:
                        self.worth_container.qp_widget = self.worth_container.query_one(
                            "#qp-widget"
                        )
                        logger.info("Found qp widget via query")
                    except Exception as e:
                        logger.error(f"Failed to find qp widget: {e}", exc_info=True)
                        return

                if self.worth_container.tp_widget is None:
                    try:
                        self.worth_container.tp_widget = self.worth_container.query_one(
                            "#tp-widget"
                        )
                        logger.info("Found tp widget via query")
                    except Exception as e:
                        logger.error(f"Failed to find tp widget: {e}", exc_info=True)
                        return

                if self.worth_container.xp_widget is None:
                    try:
                        self.worth_container.xp_widget = self.worth_container.query_one(
                            "#xp-widget"
                        )
                        logger.info("Found xp widget via query")
                    except Exception as e:
                        logger.error(f"Failed to find xp widget: {e}", exc_info=True)
                        return

                self.worth_container.gold_widget.value = (
                    str(state_manager.gold) if state_manager.gold > ZERO else "Unknown"
                )
                self.worth_container.xp_widget.value = (
                    str(state_manager.experience)
                    if state_manager.experience > ZERO
                    else "Unknown"
                )

                # Try to get worth details from GMCP
                if (
                    hasattr(state_manager, "agent")
                    and state_manager.agent is not None
                    and hasattr(state_manager.agent, "aardwolf_gmcp")
                ):
                    worth_data = state_manager.agent.aardwolf_gmcp.get_worth_data()
                    if worth_data:
                        # Create a worth update event
                        worth_update = {}

                        if "gold" in worth_data:
                            worth_update["gold"] = worth_data["gold"]
                        if "bank" in worth_data:
                            worth_update["bank"] = worth_data["bank"]
                        if "qp" in worth_data:
                            worth_update["qp"] = worth_data["qp"]
                        if "tp" in worth_data:
                            worth_update["tp"] = worth_data["tp"]
                        if "xp" in worth_data:
                            worth_update["xp"] = worth_data["xp"]

                        # Emit the worth update event if we have data
                        if worth_update and hasattr(state_manager, "events"):
                            state_manager.events.emit("worth_update", worth_update)
                            logger.debug(
                                f"Emitted worth_update event with data: {worth_update}"
                            )
            except Exception as e:
                logger.error(f"Error updating worth: {e}", exc_info=True)

            # Update stats
            try:
                # Check if stats_container is None
                if self.stats_container is None:
                    logger.warning("Stats container is None, cannot update stats")
                    # Try to find the stats container
                    try:
                        self.stats_container = self.query_one("#stats-container")
                        logger.info("Found stats container via query")
                    except Exception as e:
                        logger.error(
                            f"Failed to find stats container: {e}", exc_info=True
                        )
                        return

                # Check if stats_container is mounted
                if (
                    not hasattr(self.stats_container, "is_mounted")
                    or not self.stats_container.is_mounted
                ):
                    logger.debug("Stats container not mounted yet, deferring update")
                    # Schedule another update after a short delay using asyncio to avoid blocking
                    import asyncio
                    asyncio.create_task(self._deferred_update(state_manager))
                    return

                # First try to get stats from GMCP
                if (
                    hasattr(state_manager, "agent")
                    and state_manager.agent is not None
                    and hasattr(state_manager.agent, "aardwolf_gmcp")
                ):
                    gmcp = state_manager.agent.aardwolf_gmcp

                    # Get regular stats
                    stats_data = gmcp.get_stats_data()
                    if stats_data:
                        # Check if the child widgets are initialized
                        if self.stats_container.str_widget is None:
                            try:
                                self.stats_container.str_widget = (
                                    self.stats_container.query_one("#str-widget")
                                )
                                logger.info("Found str widget via query")
                            except Exception as e:
                                logger.error(
                                    f"Failed to find str widget: {e}", exc_info=True
                                )
                                return

                        if self.stats_container.int_widget is None:
                            try:
                                self.stats_container.int_widget = (
                                    self.stats_container.query_one("#int-widget")
                                )
                                logger.info("Found int widget via query")
                            except Exception as e:
                                logger.error(
                                    f"Failed to find int widget: {e}", exc_info=True
                                )
                                return

                        if self.stats_container.wis_widget is None:
                            try:
                                self.stats_container.wis_widget = (
                                    self.stats_container.query_one("#wis-widget")
                                )
                                logger.info("Found wis widget via query")
                            except Exception as e:
                                logger.error(
                                    f"Failed to find wis widget: {e}", exc_info=True
                                )
                                return

                        if self.stats_container.dex_widget is None:
                            try:
                                self.stats_container.dex_widget = (
                                    self.stats_container.query_one("#dex-widget")
                                )
                                logger.info("Found dex widget via query")
                            except Exception as e:
                                logger.error(
                                    f"Failed to find dex widget: {e}", exc_info=True
                                )
                                return

                        if self.stats_container.con_widget is None:
                            try:
                                self.stats_container.con_widget = (
                                    self.stats_container.query_one("#con-widget")
                                )
                                logger.info("Found con widget via query")
                            except Exception as e:
                                logger.error(
                                    f"Failed to find con widget: {e}", exc_info=True
                                )
                                return

                        if self.stats_container.luck_widget is None:
                            try:
                                self.stats_container.luck_widget = (
                                    self.stats_container.query_one("#luck-widget")
                                )
                                logger.info("Found luck widget via query")
                            except Exception as e:
                                logger.error(
                                    f"Failed to find luck widget: {e}", exc_info=True
                                )
                                return

                        if self.stats_container.hr_widget is None:
                            try:
                                self.stats_container.hr_widget = (
                                    self.stats_container.query_one("#hr-widget")
                                )
                                logger.info("Found hr widget via query")
                            except Exception as e:
                                logger.error(
                                    f"Failed to find hr widget: {e}", exc_info=True
                                )
                                return

                        if self.stats_container.dr_widget is None:
                            try:
                                self.stats_container.dr_widget = (
                                    self.stats_container.query_one("#dr-widget")
                                )
                                logger.info("Found dr widget via query")
                            except Exception as e:
                                logger.error(
                                    f"Failed to find dr widget: {e}", exc_info=True
                                )
                                return

                        # Update individual stat widgets
                        if "str" in stats_data:
                            # Check if it's a static widget
                            if hasattr(
                                self.stats_container.str_widget, "current_value"
                            ):
                                self.stats_container.str_widget.current_value = (
                                    stats_data["str"]
                                )
                            else:
                                self.stats_container.str_widget.value = stats_data[
                                    "str"
                                ]
                        if "int" in stats_data:
                            # Check if it's a static widget
                            if hasattr(
                                self.stats_container.int_widget, "current_value"
                            ):
                                self.stats_container.int_widget.current_value = (
                                    stats_data["int"]
                                )
                            else:
                                self.stats_container.int_widget.value = stats_data[
                                    "int"
                                ]
                        if "wis" in stats_data:
                            # Check if it's a static widget
                            if hasattr(
                                self.stats_container.wis_widget, "current_value"
                            ):
                                self.stats_container.wis_widget.current_value = (
                                    stats_data["wis"]
                                )
                            else:
                                self.stats_container.wis_widget.value = stats_data[
                                    "wis"
                                ]
                        if "dex" in stats_data:
                            # Check if it's a static widget
                            if hasattr(
                                self.stats_container.dex_widget, "current_value"
                            ):
                                self.stats_container.dex_widget.current_value = (
                                    stats_data["dex"]
                                )
                            else:
                                self.stats_container.dex_widget.value = stats_data[
                                    "dex"
                                ]
                        if "con" in stats_data:
                            # Check if it's a static widget
                            if hasattr(
                                self.stats_container.con_widget, "current_value"
                            ):
                                self.stats_container.con_widget.current_value = (
                                    stats_data["con"]
                                )
                            else:
                                self.stats_container.con_widget.value = stats_data[
                                    "con"
                                ]
                        if "luck" in stats_data:
                            # Check if it's a static widget
                            if hasattr(
                                self.stats_container.luck_widget, "current_value"
                            ):
                                self.stats_container.luck_widget.current_value = (
                                    stats_data["luck"]
                                )
                            else:
                                self.stats_container.luck_widget.value = stats_data[
                                    "luck"
                                ]
                        if "hr" in stats_data:
                            # Check if it's a static widget
                            if hasattr(self.stats_container.hr_widget, "current_value"):
                                self.stats_container.hr_widget.current_value = (
                                    stats_data["hr"]
                                )
                            else:
                                self.stats_container.hr_widget.value = stats_data["hr"]
                        if "dr" in stats_data:
                            # Check if it's a static widget
                            if hasattr(self.stats_container.dr_widget, "current_value"):
                                self.stats_container.dr_widget.current_value = (
                                    stats_data["dr"]
                                )
                            else:
                                self.stats_container.dr_widget.value = stats_data["dr"]

                    # Get max stats
                    max_stats = gmcp.get_maxstats_data()
                    if max_stats:
                        # Update individual stat widget max values
                        if "maxstr" in max_stats:
                            # Check if it's a static widget
                            if hasattr(self.stats_container.str_widget, "max_value"):
                                self.stats_container.str_widget.max_value = max_stats[
                                    "maxstr"
                                ]
                            else:
                                self.stats_container.str_widget.maximum = max_stats[
                                    "maxstr"
                                ]
                        if "maxint" in max_stats:
                            # Check if it's a static widget
                            if hasattr(self.stats_container.int_widget, "max_value"):
                                self.stats_container.int_widget.max_value = max_stats[
                                    "maxint"
                                ]
                            else:
                                self.stats_container.int_widget.maximum = max_stats[
                                    "maxint"
                                ]
                        if "maxwis" in max_stats:
                            # Check if it's a static widget
                            if hasattr(self.stats_container.wis_widget, "max_value"):
                                self.stats_container.wis_widget.max_value = max_stats[
                                    "maxwis"
                                ]
                            else:
                                self.stats_container.wis_widget.maximum = max_stats[
                                    "maxwis"
                                ]
                        if "maxdex" in max_stats:
                            # Check if it's a static widget
                            if hasattr(self.stats_container.dex_widget, "max_value"):
                                self.stats_container.dex_widget.max_value = max_stats[
                                    "maxdex"
                                ]
                            else:
                                self.stats_container.dex_widget.maximum = max_stats[
                                    "maxdex"
                                ]
                        if "maxcon" in max_stats:
                            # Check if it's a static widget
                            if hasattr(self.stats_container.con_widget, "max_value"):
                                self.stats_container.con_widget.max_value = max_stats[
                                    "maxcon"
                                ]
                            else:
                                self.stats_container.con_widget.maximum = max_stats[
                                    "maxcon"
                                ]
                        if "maxluck" in max_stats:
                            # Check if it's a static widget
                            if hasattr(self.stats_container.luck_widget, "max_value"):
                                self.stats_container.luck_widget.max_value = max_stats[
                                    "maxluck"
                                ]
                            else:
                                self.stats_container.luck_widget.maximum = max_stats[
                                    "maxluck"
                                ]
            except Exception as e:
                logger.error(f"Error updating stats: {e}", exc_info=True)

            # Update status effects
            try:
                # Check if status_effects is None
                if self.status_effects is None:
                    logger.warning(
                        "Status effects widget is None, cannot update status effects"
                    )
                    # Try to find the status effects widget
                    try:
                        self.status_effects = self.query_one("#status-effects-widget")
                        logger.info("Found status effects widget via query")
                    except Exception as e:
                        logger.error(
                            f"Failed to find status effects widget: {e}", exc_info=True
                        )
                        return

                # Check if status_effects is mounted
                if (
                    not hasattr(self.status_effects, "is_mounted")
                    or not self.status_effects.is_mounted
                ):
                    logger.debug(
                        "Status effects widget not mounted yet, deferring update"
                    )
                    # Schedule another update after a short delay using asyncio to avoid blocking
                    import asyncio
                    asyncio.create_task(self._deferred_update(state_manager))
                    return

                if hasattr(state_manager, "status") and state_manager.status:
                    self.status_effects.status_effects = state_manager.status
                elif (
                    hasattr(state_manager, "agent")
                    and state_manager.agent is not None
                    and hasattr(state_manager.agent, "aardwolf_gmcp")
                ):
                    char_data = state_manager.agent.aardwolf_gmcp.char_data
                    if "status" in char_data:
                        if isinstance(char_data["status"], list):
                            self.status_effects.status_effects = char_data["status"]
                        elif isinstance(char_data["status"], dict):
                            self.status_effects.status_effects = [
                                status
                                for status, active in char_data["status"].items()
                                if active
                            ]
            except Exception as e:
                logger.error(f"Error updating status effects: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error updating status container: {e}", exc_info=True)

    def on_state_manager_changed(self, state_manager):
        """Handle state manager changes.

        Args:
            state_manager: The new state manager
        """
        logger.debug("StatusContainer.on_state_manager_changed called")
        # Schedule an update with the new state manager
        if state_manager:
            import asyncio

            asyncio.create_task(self.update_from_state_manager(state_manager))

    async def update_all_widgets_directly(self, state_manager):
        """Directly update all widgets with state manager data.

        This method bypasses the event system and directly updates all widgets
        with data from the state manager.

        Args:
            state_manager: The state manager containing the state
        """
        logger.info("Directly updating all widgets with state manager data")
        try:
            # Update character header
            if self.character_header:
                self.character_header.character_name = state_manager.character_name
                self.character_header.level = state_manager.level
                self.character_header.race = state_manager.race
                self.character_header.character_class = state_manager.character_class
                self.character_header.update_content()

            # Update vitals - ensure all widgets are updated with the latest data
            if hasattr(self, "vitals_container") and self.vitals_container:
                # Update HP widget
                if (
                    hasattr(self.vitals_container, "hp_widget")
                    and self.vitals_container.hp_widget
                ):
                    if (
                        hasattr(self.vitals_container.hp_widget, "hp_current_widget")
                        and self.vitals_container.hp_widget.hp_current_widget
                    ):
                        # Get the current value from the state manager
                        hp_current = state_manager.hp_current
                        logger.info(
                            f"Setting HP current value to {hp_current} (type: {type(hp_current)})"
                        )

                        # Force update the widget value
                        self.vitals_container.hp_widget.hp_current_widget.value = (
                            hp_current
                        )
                        self.vitals_container.hp_widget.hp_current_widget.in_combat = (
                            state_manager.in_combat
                        )
                        self.vitals_container.hp_widget.hp_current_widget.update_content()

                        # Force a refresh to ensure the widget is visible
                        self.vitals_container.hp_widget.hp_current_widget.refresh()

                    if (
                        hasattr(self.vitals_container.hp_widget, "hp_max_widget")
                        and self.vitals_container.hp_widget.hp_max_widget
                    ):
                        # Get the max value from the state manager
                        hp_max = state_manager.hp_max
                        logger.info(
                            f"Setting HP max value to {hp_max} (type: {type(hp_max)})"
                        )

                        # Force update the widget value
                        self.vitals_container.hp_widget.hp_max_widget.value = hp_max
                        self.vitals_container.hp_widget.hp_max_widget.update_content()

                        # Force a refresh to ensure the widget is visible
                        self.vitals_container.hp_widget.hp_max_widget.refresh()

                    logger.info(
                        f"Updated HP widget with current={state_manager.hp_current}, max={state_manager.hp_max}"
                    )

                # Update MP widget
                if (
                    hasattr(self.vitals_container, "mp_widget")
                    and self.vitals_container.mp_widget
                ):
                    if (
                        hasattr(self.vitals_container.mp_widget, "mp_current_widget")
                        and self.vitals_container.mp_widget.mp_current_widget
                    ):
                        # Get the current value from the state manager
                        mp_current = state_manager.mp_current
                        logger.info(
                            f"Setting MP current value to {mp_current} (type: {type(mp_current)})"
                        )

                        # Force update the widget value
                        self.vitals_container.mp_widget.mp_current_widget.value = (
                            mp_current
                        )
                        self.vitals_container.mp_widget.mp_current_widget.in_combat = (
                            state_manager.in_combat
                        )
                        self.vitals_container.mp_widget.mp_current_widget.update_content()

                        # Force a refresh to ensure the widget is visible
                        self.vitals_container.mp_widget.mp_current_widget.refresh()

                    if (
                        hasattr(self.vitals_container.mp_widget, "mp_max_widget")
                        and self.vitals_container.mp_widget.mp_max_widget
                    ):
                        # Get the max value from the state manager
                        mp_max = state_manager.mp_max
                        logger.info(
                            f"Setting MP max value to {mp_max} (type: {type(mp_max)})"
                        )

                        # Force update the widget value
                        self.vitals_container.mp_widget.mp_max_widget.value = mp_max
                        self.vitals_container.mp_widget.mp_max_widget.update_content()

                        # Force a refresh to ensure the widget is visible
                        self.vitals_container.mp_widget.mp_max_widget.refresh()

                    logger.info(
                        f"Updated MP widget with current={state_manager.mp_current}, max={state_manager.mp_max}"
                    )

                # Update MV widget
                if (
                    hasattr(self.vitals_container, "mv_widget")
                    and self.vitals_container.mv_widget
                ):
                    if (
                        hasattr(self.vitals_container.mv_widget, "mv_current_widget")
                        and self.vitals_container.mv_widget.mv_current_widget
                    ):
                        # Get the current value from the state manager
                        mv_current = state_manager.mv_current
                        logger.info(
                            f"Setting MV current value to {mv_current} (type: {type(mv_current)})"
                        )

                        # Force update the widget value
                        self.vitals_container.mv_widget.mv_current_widget.value = (
                            mv_current
                        )
                        self.vitals_container.mv_widget.mv_current_widget.in_combat = (
                            state_manager.in_combat
                        )
                        self.vitals_container.mv_widget.mv_current_widget.update_content()

                        # Force a refresh to ensure the widget is visible
                        self.vitals_container.mv_widget.mv_current_widget.refresh()

                    if (
                        hasattr(self.vitals_container.mv_widget, "mv_max_widget")
                        and self.vitals_container.mv_widget.mv_max_widget
                    ):
                        # Get the max value from the state manager
                        mv_max = state_manager.mv_max
                        logger.info(
                            f"Setting MV max value to {mv_max} (type: {type(mv_max)})"
                        )

                        # Force update the widget value
                        self.vitals_container.mv_widget.mv_max_widget.value = mv_max
                        self.vitals_container.mv_widget.mv_max_widget.update_content()

                        # Force a refresh to ensure the widget is visible
                        self.vitals_container.mv_widget.mv_max_widget.refresh()

                    logger.info(
                        f"Updated MV widget with current={state_manager.mv_current}, max={state_manager.mv_max}"
                    )

                # Update hunger widget in vitals container
                if (
                    hasattr(self.vitals_container, "hunger_widget")
                    and self.vitals_container.hunger_widget
                ):
                    # Update hunger widget
                    self.vitals_container.hunger_widget.current = state_manager.hunger[
                        "current"
                    ]
                    self.vitals_container.hunger_widget.maximum = state_manager.hunger[
                        "max"
                    ]

                    # Calculate text representation for hunger
                    if state_manager.hunger["max"] > 0:
                        hunger_percent = int(
                            (
                                state_manager.hunger["current"]
                                / state_manager.hunger["max"]
                            )
                            * ONE_HUNDRED_PERCENT
                        )
                        self.vitals_container.hunger_widget.text = (
                            "Full"
                            if hunger_percent > FULL_THRESHOLD
                            else "Satiated"
                            if hunger_percent > SATIATED_THRESHOLD
                            else "Hungry"
                            if hunger_percent > HUNGRY_THRESHOLD
                            else "Starving"
                        )
                    self.vitals_container.hunger_widget.update_content()
                    logger.info(
                        f"Updated hunger widget in vitals container: {state_manager.hunger['current']}/{state_manager.hunger['max']}"
                    )

                # Update thirst widget in vitals container
                if (
                    hasattr(self.vitals_container, "thirst_widget")
                    and self.vitals_container.thirst_widget
                ):
                    # Update thirst widget
                    self.vitals_container.thirst_widget.current = state_manager.thirst[
                        "current"
                    ]
                    self.vitals_container.thirst_widget.maximum = state_manager.thirst[
                        "max"
                    ]

                    # Calculate text representation for thirst
                    if state_manager.thirst["max"] > 0:
                        thirst_percent = int(
                            (
                                state_manager.thirst["current"]
                                / state_manager.thirst["max"]
                            )
                            * ONE_HUNDRED_PERCENT
                        )
                        self.vitals_container.thirst_widget.text = (
                            "Quenched"
                            if thirst_percent > FULL_THRESHOLD
                            else "Not Thirsty"
                            if thirst_percent > SATIATED_THRESHOLD
                            else "Thirsty"
                            if thirst_percent > HUNGRY_THRESHOLD
                            else "Parched"
                        )
                    self.vitals_container.thirst_widget.update_content()
                    logger.info(
                        f"Updated thirst widget in vitals container: {state_manager.thirst['current']}/{state_manager.thirst['max']}"
                    )

                # Force a refresh of the entire vitals container to ensure all widgets are visible
                self.vitals_container.refresh()
                logger.info("Refreshed entire vitals container")

            # Update stats
            if hasattr(self, "stats_container") and self.stats_container:
                # Try to get stats from GMCP
                if (
                    hasattr(state_manager, "agent")
                    and state_manager.agent is not None
                    and hasattr(state_manager.agent, "aardwolf_gmcp")
                ):
                    gmcp = state_manager.agent.aardwolf_gmcp
                    stats_data = gmcp.get_stats_data()
                    max_stats = gmcp.get_maxstats_data()

                    if stats_data and max_stats:
                        logger.info(f"Using GMCP stats data: {stats_data}")
                        logger.info(f"Using GMCP max stats data: {max_stats}")

                        # Update STR widget
                        if (
                            hasattr(self.stats_container, "str_widget")
                            and self.stats_container.str_widget
                        ):
                            if "str" in stats_data:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.str_widget, "current_value"
                                ):
                                    self.stats_container.str_widget.current_value = (
                                        stats_data["str"]
                                    )
                                else:
                                    self.stats_container.str_widget.value = stats_data[
                                        "str"
                                    ]
                            if "maxstr" in max_stats:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.str_widget, "max_value"
                                ):
                                    self.stats_container.str_widget.max_value = (
                                        max_stats["maxstr"]
                                    )
                                else:
                                    self.stats_container.str_widget.maximum = max_stats[
                                        "maxstr"
                                    ]

                            # Update display based on widget type
                            if hasattr(
                                self.stats_container.str_widget, "update_display"
                            ):
                                self.stats_container.str_widget.update_display()
                            else:
                                self.stats_container.str_widget.update_content()

                            logger.info(
                                f"Updated STR widget with current/value={stats_data.get('str', 'N/A')}, max={max_stats.get('maxstr', 'N/A')}"
                            )

                        # Update INT widget
                        if (
                            hasattr(self.stats_container, "int_widget")
                            and self.stats_container.int_widget
                        ):
                            if "int" in stats_data:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.int_widget, "current_value"
                                ):
                                    self.stats_container.int_widget.current_value = (
                                        stats_data["int"]
                                    )
                                else:
                                    self.stats_container.int_widget.value = stats_data[
                                        "int"
                                    ]
                            if "maxint" in max_stats:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.int_widget, "max_value"
                                ):
                                    self.stats_container.int_widget.max_value = (
                                        max_stats["maxint"]
                                    )
                                else:
                                    self.stats_container.int_widget.maximum = max_stats[
                                        "maxint"
                                    ]

                            # Update display based on widget type
                            if hasattr(
                                self.stats_container.int_widget, "update_display"
                            ):
                                self.stats_container.int_widget.update_display()
                            else:
                                self.stats_container.int_widget.update_content()

                            logger.info(
                                f"Updated INT widget with current/value={stats_data.get('int', 'N/A')}, max={max_stats.get('maxint', 'N/A')}"
                            )

                        # Update WIS widget
                        if (
                            hasattr(self.stats_container, "wis_widget")
                            and self.stats_container.wis_widget
                        ):
                            if "wis" in stats_data:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.wis_widget, "current_value"
                                ):
                                    self.stats_container.wis_widget.current_value = (
                                        stats_data["wis"]
                                    )
                                else:
                                    self.stats_container.wis_widget.value = stats_data[
                                        "wis"
                                    ]
                            if "maxwis" in max_stats:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.wis_widget, "max_value"
                                ):
                                    self.stats_container.wis_widget.max_value = (
                                        max_stats["maxwis"]
                                    )
                                else:
                                    self.stats_container.wis_widget.maximum = max_stats[
                                        "maxwis"
                                    ]

                            # Update display based on widget type
                            if hasattr(
                                self.stats_container.wis_widget, "update_display"
                            ):
                                self.stats_container.wis_widget.update_display()
                            else:
                                self.stats_container.wis_widget.update_content()

                            logger.info(
                                f"Updated WIS widget with current/value={stats_data.get('wis', 'N/A')}, max={max_stats.get('maxwis', 'N/A')}"
                            )

                        # Update DEX widget
                        if (
                            hasattr(self.stats_container, "dex_widget")
                            and self.stats_container.dex_widget
                        ):
                            if "dex" in stats_data:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.dex_widget, "current_value"
                                ):
                                    self.stats_container.dex_widget.current_value = (
                                        stats_data["dex"]
                                    )
                                else:
                                    self.stats_container.dex_widget.value = stats_data[
                                        "dex"
                                    ]
                            if "maxdex" in max_stats:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.dex_widget, "max_value"
                                ):
                                    self.stats_container.dex_widget.max_value = (
                                        max_stats["maxdex"]
                                    )
                                else:
                                    self.stats_container.dex_widget.maximum = max_stats[
                                        "maxdex"
                                    ]

                            # Update display based on widget type
                            if hasattr(
                                self.stats_container.dex_widget, "update_display"
                            ):
                                self.stats_container.dex_widget.update_display()
                            else:
                                self.stats_container.dex_widget.update_content()

                            logger.info(
                                f"Updated DEX widget with current/value={stats_data.get('dex', 'N/A')}, max={max_stats.get('maxdex', 'N/A')}"
                            )

                        # Update CON widget
                        if (
                            hasattr(self.stats_container, "con_widget")
                            and self.stats_container.con_widget
                        ):
                            if "con" in stats_data:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.con_widget, "current_value"
                                ):
                                    self.stats_container.con_widget.current_value = (
                                        stats_data["con"]
                                    )
                                else:
                                    self.stats_container.con_widget.value = stats_data[
                                        "con"
                                    ]
                            if "maxcon" in max_stats:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.con_widget, "max_value"
                                ):
                                    self.stats_container.con_widget.max_value = (
                                        max_stats["maxcon"]
                                    )
                                else:
                                    self.stats_container.con_widget.maximum = max_stats[
                                        "maxcon"
                                    ]

                            # Update display based on widget type
                            if hasattr(
                                self.stats_container.con_widget, "update_display"
                            ):
                                self.stats_container.con_widget.update_display()
                            else:
                                self.stats_container.con_widget.update_content()

                            logger.info(
                                f"Updated CON widget with current/value={stats_data.get('con', 'N/A')}, max={max_stats.get('maxcon', 'N/A')}"
                            )

                        # Update LUCK widget
                        if (
                            hasattr(self.stats_container, "luck_widget")
                            and self.stats_container.luck_widget
                        ):
                            if "luck" in stats_data:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.luck_widget, "current_value"
                                ):
                                    self.stats_container.luck_widget.current_value = (
                                        stats_data["luck"]
                                    )
                                else:
                                    self.stats_container.luck_widget.value = stats_data[
                                        "luck"
                                    ]
                            if "maxluck" in max_stats:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.luck_widget, "max_value"
                                ):
                                    self.stats_container.luck_widget.max_value = (
                                        max_stats["maxluck"]
                                    )
                                else:
                                    self.stats_container.luck_widget.maximum = (
                                        max_stats["maxluck"]
                                    )

                            # Update display based on widget type
                            if hasattr(
                                self.stats_container.luck_widget, "update_display"
                            ):
                                self.stats_container.luck_widget.update_display()
                            else:
                                self.stats_container.luck_widget.update_content()

                            logger.info(
                                f"Updated LUCK widget with current/value={stats_data.get('luck', 'N/A')}, max={max_stats.get('maxluck', 'N/A')}"
                            )

                        # Update HR widget
                        if (
                            hasattr(self.stats_container, "hr_widget")
                            and self.stats_container.hr_widget
                        ):
                            if "hr" in stats_data:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.hr_widget, "current_value"
                                ):
                                    self.stats_container.hr_widget.current_value = (
                                        stats_data["hr"]
                                    )
                                else:
                                    self.stats_container.hr_widget.value = stats_data[
                                        "hr"
                                    ]

                            # Update display based on widget type
                            if hasattr(
                                self.stats_container.hr_widget, "update_display"
                            ):
                                self.stats_container.hr_widget.update_display()
                            else:
                                self.stats_container.hr_widget.update_content()

                            logger.info(
                                f"Updated HR widget with value={stats_data.get('hr', 'N/A')}"
                            )

                        # Update DR widget
                        if (
                            hasattr(self.stats_container, "dr_widget")
                            and self.stats_container.dr_widget
                        ):
                            if "dr" in stats_data:
                                # Check if it's a static widget
                                if hasattr(
                                    self.stats_container.dr_widget, "current_value"
                                ):
                                    self.stats_container.dr_widget.current_value = (
                                        stats_data["dr"]
                                    )
                                else:
                                    self.stats_container.dr_widget.value = stats_data[
                                        "dr"
                                    ]

                            # Update display based on widget type
                            if hasattr(
                                self.stats_container.dr_widget, "update_display"
                            ):
                                self.stats_container.dr_widget.update_display()
                            else:
                                self.stats_container.dr_widget.update_content()

                            # Force a refresh to ensure the widget is visible
                            self.stats_container.dr_widget.refresh()

                            logger.info(
                                f"Updated DR widget with value={stats_data.get('dr', 'N/A')}"
                            )

                        # Force a refresh of the entire stats container to ensure all widgets are visible
                        self.stats_container.refresh()
                        logger.info("Refreshed entire stats container")
                    else:
                        logger.warning("No GMCP stats data available")
                else:
                    logger.warning("No GMCP manager available for stats data")

            # Update status effects
            if self.status_effects:
                self.status_effects.status_effects = state_manager.status_effects
                self.status_effects.update_content()
                logger.info(
                    f"Updated status effects widget with effects={state_manager.status_effects}"
                )

            # Needs are now updated in the vitals container

            # Update quest
            if hasattr(self, "quest_widget") and self.quest_widget:
                # self.quest_widget.quest = state_manager.quests
                # self.quest_widget.target = state_manager.quest_target
                # self.quest_widget.room = state_manager.quest_room
                # self.quest_widget.area = state_manager.quest_area
                # self.quest_widget.status = state_manager.quest_status
                # self.quest_widget.update_content()
                # logger.info(f"Updated quest widget with quest={state_manager.quests}, target={state_manager.quest_target}")
                pass

            # Force a refresh of the entire status container to ensure all widgets are visible
            self.refresh()
            logger.info("Refreshed entire status container")

            logger.info("Successfully updated all widgets directly")
        except Exception as e:
            logger.error(f"Error updating widgets directly: {e}", exc_info=True)

    def update_status(self, room_name, room_number, exits, character_data):
        """Update status information - compatibility method for widget_updater.

        Args:
            room_name: Name of the current room
            room_number: Number/ID of the current room
            exits: Available exits from the room
            character_data: Character status and stats data
        """
        logger.info(f"StatusContainer.update_status called with room={room_name}, exits={exits}")

        # For now, we'll delegate to the existing update_from_state_manager method
        # This maintains compatibility while using the existing update logic
        try:
            # Get the state manager from the app if available
            if hasattr(self.app, 'state_manager') and self.app.state_manager:
                self.update_from_state_manager(self.app.state_manager)
            else:
                logger.warning("No state manager available for status update")
        except Exception as e:
            logger.error(f"Error in update_status: {e}", exc_info=True)


class RoomInfoMapContainer(ScrollableContainer):
    """Container for room info and map widgets (vertical layout)."""

    DEFAULT_CSS = """
    RoomInfoMapContainer {
        layout: vertical;
        width: 100%;
        height: auto;
        margin: 0;
        padding: 0;
        background: transparent;
        border: none;
    }
    /* Room widget styling */
    #room-info-widget {
        width: 100%;
        height: 1fr;
        content-align: left top;
        padding: 1;
        overflow: auto;
        text-align: left;
        margin: 0;
        border: none;
        background: $surface-darken-1;
    }

    /* Style for monospace text in the map widget */
    #room-info-widget .monospace {
        background: $surface;
        color: $text;
        padding: 0;
        margin: 0;
    }

    #mapper-container {
        height: 1fr;
        border: round $primary;
    }

    #z-0 #z-1 #z-2 {
        layout: grid;
        grid-size: 7 11;
        grid-columns: 1fr 1fr 1fr 1fr 1fr 1fr 1fr;
        grid-rows: 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr;
        width: 100%;
        height: 33;
        min-height: 33;
        padding: 0;
        margin: 0;
        background: $surface-darken-2;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_info_widget = None
        self.mapper_container = None

    def compose(self):
        self.room_info_widget = RoomWidget(id="room-info-widget")
        yield self.room_info_widget
        self.mapper_container = MapperContainer(id="mapper-container")
        yield self.mapper_container

    def update_from_state_manager(self, room_manager):
        """Update both child widgets from the room manager's state."""
        if self.room_info_widget and hasattr(
            self.room_info_widget, "update_from_state_manager"
        ):
            self.room_info_widget.update_from_state_manager(room_manager)
        if self.mapper_container and hasattr(
            self.mapper_container, "update_from_state_manager"
        ):
            self.mapper_container.update_from_state_manager(room_manager)

    def update_content(self):
        """Update content for both child widgets."""
        if self.room_info_widget and hasattr(self.room_info_widget, "update_content"):
            self.room_info_widget.update_content()
        if self.mapper_container and hasattr(self.mapper_container, "update_content"):
            self.mapper_container.update_content()
