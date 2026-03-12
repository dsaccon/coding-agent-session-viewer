"""Custom widgets for the session viewer."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Collapsible, Static

from claude_session_viewer.parser import ToolCall


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
            if len(result_text) > 500:
                result_text = result_text[:500] + "\n... (truncated)"
            detail_lines.append(f"\nResult:\n{result_text}")

        detail = "\n".join(detail_lines) if detail_lines else "(no details)"

        yield Collapsible(
            Static(detail, classes="tool-input", markup=False),
            title=title,
            collapsed=True,
        )
