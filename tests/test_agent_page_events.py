from PySide6.QtWidgets import QApplication

from core.event_bus import EventBus
from ui.settings.pages.agent_page import AgentPage


def _app():
    app = QApplication.instance()
    return app or QApplication([])


def test_agent_page_teardown_unsubscribes_all_handlers():
    _app()
    bus = EventBus()
    page = AgentPage(event_bus_instance=bus)

    assert len(bus._handlers) > 0

    page._teardown_event_subscription()

    assert all(not handlers for handlers in bus._handlers.values())


def test_agent_page_appends_log_batch_from_bridge():
    _app()
    page = AgentPage()

    page._handle_log_batch(["a", "b"])

    assert len(page._log_entries) == 2
