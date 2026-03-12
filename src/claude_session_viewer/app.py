"""Claude Code Session Viewer — Textual TUI Application."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Label, ListItem, ListView, Static
from textual import work
from textual.worker import get_current_worker

SCROLL_STEP = 5  # lines per arrow key press in conversation


class FastScroll(VerticalScroll):
    """VerticalScroll that moves multiple lines per keypress."""

    BINDINGS = [
        ("up,k", "scroll_up_fast", "Scroll Up"),
        ("down,j", "scroll_down_fast", "Scroll Down"),
        ("pageup", "page_up", "Page Up"),
        ("pagedown", "page_down", "Page Down"),
        ("home", "scroll_home", "Top"),
        ("end", "scroll_end", "Bottom"),
    ]

    def action_scroll_up_fast(self) -> None:
        self.scroll_relative(y=-SCROLL_STEP, animate=False)

    def action_scroll_down_fast(self) -> None:
        self.scroll_relative(y=SCROLL_STEP, animate=False)

    def action_page_up(self) -> None:
        self.scroll_relative(y=-self.size.height, animate=False)

    def action_page_down(self) -> None:
        self.scroll_relative(y=self.size.height, animate=False)

from claude_session_viewer.parser import (
    DEFAULT_PROJECTS_DIR,
    ProjectInfo,
    SessionSummary,
    discover_projects,
    discover_sessions,
    load_session_summary,
    parse_session,
)
from claude_session_viewer.widgets import ToolCallWidget


class SessionViewerApp(App):
    """TUI for browsing Claude Code session transcripts."""

    CSS_PATH = "app.tcss"
    TITLE = "Claude Code Session Viewer"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("tab,right", "focus_next_panel", "Next Panel"),
        ("shift+tab,left", "focus_previous_panel", "Prev Panel"),
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, projects_dir=None):
        super().__init__()
        self.projects_dir = projects_dir or DEFAULT_PROJECTS_DIR
        self.projects: list[ProjectInfo] = []
        self.session_summaries: list[SessionSummary] = []
        self._current_project_index: int | None = None
        self._current_session_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Vertical(
                Static("Projects", classes="panel-header"),
                ListView(id="projects-list"),
                id="projects-panel",
            ),
            Vertical(
                Static("Sessions", classes="panel-header"),
                ListView(id="sessions-list"),
                id="sessions-panel",
            ),
            Vertical(
                Static("Conversation", classes="panel-header"),
                FastScroll(id="conversation-scroll", can_focus_children=False),
                id="conversation-panel",
            ),
        )
        yield Static(
            "q: quit  Tab: switch panel  Esc: back  ↑↓/j/k: scroll  PgUp/PgDn: page  Enter: select",
            id="status-bar",
        )

    def on_mount(self) -> None:
        """Load projects on startup."""
        self.projects = discover_projects(self.projects_dir)
        projects_list = self.query_one("#projects-list", ListView)
        for proj in self.projects:
            label = f"{proj.display_name} ({proj.session_count})"
            projects_list.append(ListItem(Label(label)))

        if self.projects:
            projects_list.index = 0

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle highlight changes — load sessions/conversation on navigate."""
        if event.item is None:
            return
        idx = event.list_view.index
        if idx is None:
            return

        if event.list_view.id == "projects-list":
            if idx != self._current_project_index:
                self._current_project_index = idx
                self._load_sessions(idx)
        elif event.list_view.id == "sessions-list":
            if idx != self._current_session_index:
                self._current_session_index = idx
                self._load_conversation(idx)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle Enter key on list items."""
        if event.list_view.id == "projects-list":
            # Focus sessions panel after selecting a project
            self.query_one("#sessions-list", ListView).focus()
        elif event.list_view.id == "sessions-list":
            # Focus conversation panel after selecting a session
            self.query_one("#conversation-scroll").focus()

    def _load_sessions(self, project_index: int) -> None:
        """Load sessions for the selected project (async)."""
        if project_index >= len(self.projects):
            return

        project = self.projects[project_index]
        self._current_session_index = None

        sessions_list = self.query_one("#sessions-list", ListView)
        sessions_list.clear()

        # Clear conversation when project changes
        conv = self.query_one("#conversation-scroll", FastScroll)
        conv.remove_children()

        self._load_sessions_worker(project, project_index)

    @work(thread=True, exclusive=True, group="load-sessions")
    def _load_sessions_worker(self, project: ProjectInfo, project_index: int) -> None:
        """Load session summaries in a background thread."""
        worker = get_current_worker()
        session_paths = discover_sessions(project.path)
        summaries: list[SessionSummary] = []

        for path in session_paths:
            if worker.is_cancelled:
                return
            summaries.append(load_session_summary(path))

        if worker.is_cancelled:
            return

        # Update UI from the main thread
        self.call_from_thread(self._populate_sessions, summaries, project_index)

    def _populate_sessions(self, summaries: list[SessionSummary], project_index: int) -> None:
        """Populate the sessions list (called on main thread)."""
        # Check we're still on the same project
        if self._current_project_index != project_index:
            return

        self.session_summaries = summaries
        sessions_list = self.query_one("#sessions-list", ListView)
        sessions_list.clear()

        for summary in summaries:
            start_str, end_str = self._format_session_times(summary)
            preview = (summary.first_message or "(no messages)")[:60]
            time_row = Horizontal(
                Label(start_str, classes="session-start"),
                Label(end_str, classes="session-end"),
                classes="session-time-row",
            )
            sessions_list.append(
                ListItem(Vertical(time_row, Label(preview, markup=False)))
            )

    def _load_conversation(self, session_index: int) -> None:
        """Load full conversation for the selected session (async)."""
        if session_index >= len(self.session_summaries):
            return

        summary = self.session_summaries[session_index]

        conv = self.query_one("#conversation-scroll", FastScroll)
        conv.remove_children()
        conv.mount(Static("Loading...", classes="assistant-text"))

        self._load_conversation_worker(summary, session_index)

    @work(thread=True, exclusive=True, group="load-conversation")
    def _load_conversation_worker(self, summary: SessionSummary, session_index: int) -> None:
        """Parse session in background thread."""
        worker = get_current_worker()
        session = parse_session(summary.path)

        if worker.is_cancelled:
            return

        # Build tool_use_id -> result content mapping
        tool_results_map: dict[str, str] = {}
        for msg in session.messages:
            for tr in msg.tool_results:
                tool_results_map[tr.tool_use_id] = tr.content

        # Pre-build widget data (can't create widgets off-thread)
        widget_data = []
        for msg in session.messages:
            if msg.tool_results and not msg.text:
                continue

            timestamp = msg.timestamp.strftime("%H:%M")

            if msg.role == "user" and msg.text:
                widget_data.append(("user-header", f"▶ You  {timestamp}"))
                widget_data.append(("user-text", msg.text))
            elif msg.role == "assistant" and msg.text:
                widget_data.append(("assistant-header", f"◆ Claude  {timestamp}"))
                widget_data.append(("assistant-text", msg.text))

            for tc in msg.tool_calls:
                result = tool_results_map.get(tc.tool_use_id, "")
                widget_data.append(("tool", (tc, result)))

        if worker.is_cancelled:
            return

        self.call_from_thread(
            self._populate_conversation, widget_data, summary, session_index
        )

    def _populate_conversation(
        self, widget_data: list, summary: SessionSummary, session_index: int
    ) -> None:
        """Mount conversation widgets on the main thread."""
        if self._current_session_index != session_index:
            return

        conv = self.query_one("#conversation-scroll", FastScroll)
        conv.remove_children()

        widgets = []
        for kind, data in widget_data:
            if kind == "tool":
                tc, result = data
                widgets.append(ToolCallWidget(tc, tool_result=result))
            elif kind in ("user-header", "assistant-header"):
                widgets.append(Static(data, classes=kind))
            else:
                widgets.append(Static(data, classes=kind, markup=False))

        conv.mount_all(widgets)

        # Update status bar
        duration = ""
        if summary.start_time and summary.end_time:
            delta = summary.end_time - summary.start_time
            minutes = int(delta.total_seconds() // 60)
            duration = f"{minutes} min"

        status = self.query_one("#status-bar", Static)
        status.update(
            f"q: quit  Tab: switch panel  Esc: back  ↑↓/j/k: scroll  PgUp/PgDn: page  Enter: select  │  "
            f"Session {summary.session_id[:8]}  {duration}  "
            f"{summary.message_count} messages"
        )

    def _format_session_times(self, summary: SessionSummary) -> tuple[str, str]:
        """Format session start and end times as separate strings."""
        if not summary.start_time:
            return ("Unknown time", "")

        start = summary.start_time
        start_str = start.strftime("%b %d, %H:%M")

        if not summary.end_time:
            return (start_str, "")

        end = summary.end_time
        if start.date() == end.date():
            return (start_str, f"→ {end.strftime('%H:%M')}")
        else:
            return (start_str, f"→ {end.strftime('%b %d, %H:%M')}")

    def action_go_back(self) -> None:
        """Go back: Conversation → Sessions → Projects."""
        panels = ["projects-list", "sessions-list", "conversation-scroll"]
        current = self._find_current_panel(panels)
        if current > 0:
            self.query_one(f"#{panels[current - 1]}").focus()

    def action_focus_next_panel(self) -> None:
        """Cycle focus to the next panel."""
        panels = ["projects-list", "sessions-list", "conversation-scroll"]
        current = self._find_current_panel(panels)
        next_id = panels[(current + 1) % len(panels)]
        self.query_one(f"#{next_id}").focus()

    def action_focus_previous_panel(self) -> None:
        """Cycle focus to the previous panel."""
        panels = ["projects-list", "sessions-list", "conversation-scroll"]
        current = self._find_current_panel(panels)
        prev_id = panels[(current - 1) % len(panels)]
        self.query_one(f"#{prev_id}").focus()

    def _find_current_panel(self, panels: list[str]) -> int:
        """Find the index of the currently focused panel."""
        focused = self.focused
        if focused is None:
            return -1
        for i, panel_id in enumerate(panels):
            widget = self.query_one(f"#{panel_id}")
            if focused is widget or focused in widget.query("*"):
                return i
        return -1


def main():
    app = SessionViewerApp()
    app.run()
