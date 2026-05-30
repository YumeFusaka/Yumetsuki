from PySide6.QtWidgets import QApplication

from config.manager import ConfigManager
from config.schema import ProactiveEventConfig
from core.event_bus import EventBus
from ui.settings.pages.agent_page import AgentPage


def _app():
    app = QApplication.instance()
    return app or QApplication([])


def test_agent_page_teardown_unsubscribes_all_handlers():
    _app()
    bus = EventBus()
    page = AgentPage(event_bus_instance=bus)

    assert len(bus._handlers) == 0

    page._teardown_event_subscription()

    assert all(not handlers for handlers in bus._handlers.values())


def test_agent_page_no_longer_exposes_runtime_log_bridge():
    _app()
    page = AgentPage()

    assert not hasattr(page, "_handle_log_batch")


def test_agent_page_dynamic_events_use_injected_system_font_tokens(tmp_path):
    _app()
    config = ConfigManager(config_dir=tmp_path)
    config.system.font_size = 24
    config.agent.proactive.events = [
        ProactiveEventConfig(name="morning", type="timer", cooldown_minutes=30)
    ]

    page = AgentPage(config=config)

    try:
        assert page._mgr is config
        assert page._config is config.agent
        assert page._events_list.item(0).font().pointSize() == 16
    finally:
        page.close()
