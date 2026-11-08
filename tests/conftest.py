import pytest

from watcher import sources


@pytest.fixture(autouse=True)
def no_pause_between_pages(monkeypatch):
    """The real run waits a moment between two pages of a board. Tests do not."""
    monkeypatch.setattr(sources, "PAGE_PAUSE", 0)
