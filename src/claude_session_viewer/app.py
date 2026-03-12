"""Claude Code Session Viewer — Textual TUI Application."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Label, ListItem, ListView, Static

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
                VerticalScroll(id="conversation-scroll"),
                id="conversation-panel",
            ),
        )
        yield Static(
            "q: quit  Tab: switch panel  Esc: back  ↑↓: navigate  Enter: select/expand",
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
        """Load sessions for the selected project."""
        if project_index >= len(self.projects):
            return

        project = self.projects[project_index]
        session_paths = discover_sessions(project.path)

        self.session_summaries = [load_session_summary(p) for p in session_paths]
        self._current_session_index = None

        sessions_list = self.query_one("#sessions-list", ListView)
        sessions_list.clear()

        for summary in self.session_summaries:
            time_str = self._format_session_time(summary)
            preview = (summary.first_message or "(no messages)")[:60]
            item_text = f"{time_str}\n{preview}"
            sessions_list.append(ListItem(Label(item_text)))

        # Clear conversation when project changes
        conv = self.query_one("#conversation-scroll", VerticalScroll)
        conv.remove_children()

    def _load_conversation(self, session_index: int) -> None:
        """Load full conversation for the selected session."""
        if session_index >= len(self.session_summaries):
            return

        summary = self.session_summaries[session_index]
        session = parse_session(summary.path)

        # Build tool_use_id -> result content mapping
        tool_results_map: dict[str, str] = {}
        for msg in session.messages:
            for tr in msg.tool_results:
                tool_results_map[tr.tool_use_id] = tr.content

        conv = self.query_one("#conversation-scroll", VerticalScroll)
        conv.remove_children()

        for msg in session.messages:
            if msg.tool_results and not msg.text:
                # Pure tool result messages are shown via the tool call widget
                continue

            timestamp = msg.timestamp.strftime("%H:%M")

            if msg.role == "user" and msg.text:
                conv.mount(Static(f"▶ You  {timestamp}", classes="user-header"))
                conv.mount(Static(msg.text, classes="message-text"))
            elif msg.role == "assistant" and msg.text:
                conv.mount(
                    Static(f"◆ Claude  {timestamp}", classes="assistant-header")
                )
                conv.mount(Static(msg.text, classes="message-text"))

            for tc in msg.tool_calls:
                result = tool_results_map.get(tc.tool_use_id, "")
                conv.mount(ToolCallWidget(tc, tool_result=result))

        # Update status bar
        duration = ""
        if summary.start_time and summary.end_time:
            delta = summary.end_time - summary.start_time
            minutes = int(delta.total_seconds() // 60)
            duration = f"{minutes} min"

        status = self.query_one("#status-bar", Static)
        status.update(
            f"q: quit  Tab: switch panel  Esc: back  ↑↓: navigate  Enter: select/expand  │  "
            f"Session {summary.session_id[:8]}  {duration}  "
            f"{summary.message_count} messages"
        )

    def _format_session_time(self, summary: SessionSummary) -> str:
        """Format session start → end time."""
        if not summary.start_time:
            return "Unknown time"

        start = summary.start_time
        start_str = start.strftime("%b %d, %H:%M")

        if not summary.end_time:
            return start_str

        end = summary.end_time
        if start.date() == end.date():
            return f"{start_str} → {end.strftime('%H:%M')}"
        else:
            return f"{start_str} → {end.strftime('%b %d, %H:%M')}"

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
