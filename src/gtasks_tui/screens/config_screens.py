"""Filter screen for the task list."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Select, Static


_DAYS_OPTIONS: list[tuple[str, int | None]] = [
    ("All time", None),
    ("Last 7 days", 7),
    ("Last 14 days", 14),
    ("Last 30 days", 30),
    ("Last 90 days", 90),
]


class FilterScreen(ModalScreen):
    """Quick filter — set a recency window for completed tasks."""

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, filter_days: int | None = None) -> None:
        super().__init__()
        self._filter_days = filter_days

    def compose(self) -> ComposeResult:
        with Vertical(id="filter-dialog"):
            yield Label("FILTER", id="filter-title")
            yield Select(
                [(label, val) for label, val in _DAYS_OPTIONS],
                value=self._filter_days,
                id="filter-days",
                prompt="Show completed",
            )
            yield Static("esc  close", id="filter-hint")

    def action_close(self) -> None:
        days_select = self.query_one("#filter-days", Select)
        days = days_select.value if days_select.value is not Select.BLANK else None
        self.dismiss({"days": days})
