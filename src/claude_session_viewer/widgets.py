"""Custom widgets for the session viewer."""

from __future__ import annotations

import os

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Collapsible, Static

from claude_session_viewer.parser import ToolCall

MAX_DIFF_LINES = 80
MAX_WRITE_LINES = 40
MAX_RESULT_CHARS = 500


def _short_path(file_path: str) -> str:
    """Shorten a file path by collapsing the home directory."""
    home = os.path.expanduser("~")
    if file_path.startswith(home):
        return "~" + file_path[len(home):]
    return file_path


class ToolCallWidget(Static):
    """A collapsible tool call display."""

    DEFAULT_CSS = """
    ToolCallWidget {
        margin: 0;
    }
    ToolCallWidget Collapsible {
        padding: 0;
    }
    ToolCallWidget .tool-input {
        color: $text-muted;
        margin: 0 0 0 2;
    }
    """

    def __init__(self, tool_call: ToolCall, tool_result: str = ""):
        super().__init__()
        self.tool_call = tool_call
        self.tool_result = tool_result

    def compose(self) -> ComposeResult:
        tc = self.tool_call
        if tc.name == "Edit":
            yield from self._compose_edit()
        elif tc.name == "Write":
            yield from self._compose_write()
        else:
            yield from self._compose_default()

    def _compose_edit(self) -> ComposeResult:
        tc = self.tool_call
        file_path = tc.input.get("file_path", "")
        old_string = tc.input.get("old_string", "")
        new_string = tc.input.get("new_string", "")

        short = _short_path(file_path)
        title = f"✎ Edit  {short}"

        diff = Text()
        old_lines = old_string.splitlines() if old_string else []
        new_lines = new_string.splitlines() if new_string else []
        total = len(old_lines) + len(new_lines)

        for line in old_lines[:MAX_DIFF_LINES]:
            diff.append("- ", style="bold red")
            diff.append(line + "\n", style="red")
        if old_lines and new_lines:
            diff.append("\n")
        for line in new_lines[:MAX_DIFF_LINES]:
            diff.append("+ ", style="bold green")
            diff.append(line + "\n", style="green")

        if total > MAX_DIFF_LINES * 2:
            diff.append(f"\n... ({total} lines total, truncated)\n", style="dim")

        self._append_error(diff)

        yield Collapsible(
            Static(diff, classes="tool-input"),
            title=title,
            collapsed=True,
        )

    def _compose_write(self) -> ComposeResult:
        tc = self.tool_call
        file_path = tc.input.get("file_path", "")
        content = tc.input.get("content", "")

        short = _short_path(file_path)
        title = f"✎ Write  {short}"

        diff = Text()
        lines = content.splitlines() if content else []
        for line in lines[:MAX_WRITE_LINES]:
            diff.append("+ ", style="bold green")
            diff.append(line + "\n", style="green")

        if len(lines) > MAX_WRITE_LINES:
            diff.append(
                f"\n... ({len(lines)} lines total, truncated)\n", style="dim"
            )

        self._append_error(diff)

        yield Collapsible(
            Static(diff, classes="tool-input"),
            title=title,
            collapsed=True,
        )

    def _compose_default(self) -> ComposeResult:
        tc = self.tool_call
        input_preview = ""
        if tc.input:
            first_val = next(iter(tc.input.values()), "")
            if isinstance(first_val, str):
                input_preview = f' "{first_val[:60]}"'

        title = f"▸ {tc.name}{input_preview}"

        detail_lines = []
        if tc.input:
            for key, val in tc.input.items():
                val_str = str(val)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                detail_lines.append(f"{key}: {val_str}")

        if self.tool_result:
            result_text = self.tool_result
            if len(result_text) > MAX_RESULT_CHARS:
                result_text = result_text[:MAX_RESULT_CHARS] + "\n... (truncated)"
            detail_lines.append(f"\nResult:\n{result_text}")

        detail = "\n".join(detail_lines) if detail_lines else "(no details)"

        yield Collapsible(
            Static(detail, classes="tool-input", markup=False),
            title=title,
            collapsed=True,
        )

    def _append_error(self, text: Text) -> None:
        """Append tool result if it's an error."""
        if self.tool_result and "error" in self.tool_result.lower():
            text.append("\n")
            text.append(self.tool_result[:MAX_RESULT_CHARS], style="bold red")
