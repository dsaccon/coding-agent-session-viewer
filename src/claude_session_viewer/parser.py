"""Parse Claude Code session JSONL files."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ToolCall:
    name: str
    input: dict
    tool_use_id: str = ""


@dataclass
class ToolResult:
    tool_use_id: str
    content: str


@dataclass
class Message:
    type: str  # "user" or "assistant"
    role: str
    timestamp: datetime
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    uuid: str = ""


@dataclass
class SessionData:
    session_id: str
    path: Path
    start_time: datetime | None = None
    end_time: datetime | None = None
    first_message: str = ""
    messages: list[Message] = field(default_factory=list)


@dataclass
class SessionSummary:
    session_id: str
    path: Path
    start_time: datetime | None = None
    end_time: datetime | None = None
    first_message: str = ""
    message_count: int = 0


@dataclass
class ProjectInfo:
    path: Path
    display_name: str
    session_count: int = 0


# Default Claude projects directory
DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _parse_timestamp(ts: str) -> datetime:
    """Parse ISO timestamp string."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _extract_message(raw: dict) -> Message | None:
    """Extract a Message from a raw JSONL line dict."""
    msg_type = raw.get("type")
    if msg_type not in ("user", "assistant"):
        return None

    msg_data = raw.get("message", {})
    role = msg_data.get("role", msg_type)
    timestamp = _parse_timestamp(raw["timestamp"])
    content = msg_data.get("content", "")

    text = ""
    tool_calls = []
    tool_results = []

    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text_parts = []
        for block in content:
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        name=block.get("name", ""),
                        input=block.get("input", {}),
                        tool_use_id=block.get("id", ""),
                    )
                )
            elif block_type == "tool_result":
                result_content = block.get("content", "")
                if isinstance(result_content, list):
                    result_content = "\n".join(
                        b.get("text", "")
                        for b in result_content
                        if b.get("type") == "text"
                    )
                tool_results.append(
                    ToolResult(
                        tool_use_id=block.get("tool_use_id", ""),
                        content=result_content,
                    )
                )
        text = "\n".join(text_parts)

    return Message(
        type=msg_type,
        role=role,
        timestamp=timestamp,
        text=text,
        tool_calls=tool_calls,
        tool_results=tool_results,
        uuid=raw.get("uuid", ""),
    )


def parse_session(path: Path) -> SessionData:
    """Parse a JSONL session file into a SessionData object."""
    session_id = path.stem
    messages: list[Message] = []
    first_user_message = ""
    start_time: datetime | None = None
    end_time: datetime | None = None

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "timestamp" in raw:
                ts = _parse_timestamp(raw["timestamp"])
                if start_time is None or ts < start_time:
                    start_time = ts
                if end_time is None or ts > end_time:
                    end_time = ts

            msg = _extract_message(raw)
            if msg is None:
                continue
            messages.append(msg)

            if not first_user_message and msg.role == "user" and msg.text:
                first_user_message = msg.text

    return SessionData(
        session_id=session_id,
        path=path,
        start_time=start_time,
        end_time=end_time,
        first_message=first_user_message,
        messages=messages,
    )


def load_session_summary(path: Path) -> SessionSummary:
    """Load just the metadata from a session file without parsing all messages."""
    session_id = path.stem
    start_time: datetime | None = None
    end_time: datetime | None = None
    first_message = ""
    message_count = 0

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "timestamp" in raw:
                ts = _parse_timestamp(raw["timestamp"])
                if start_time is None or ts < start_time:
                    start_time = ts
                if end_time is None or ts > end_time:
                    end_time = ts

            msg_type = raw.get("type")
            if msg_type in ("user", "assistant"):
                message_count += 1
                if not first_message and msg_type == "user":
                    msg_data = raw.get("message", {})
                    content = msg_data.get("content", "")
                    if isinstance(content, str):
                        first_message = content
                    elif isinstance(content, list):
                        for block in content:
                            if block.get("type") == "text":
                                first_message = block.get("text", "")
                                break

    return SessionSummary(
        session_id=session_id,
        path=path,
        start_time=start_time,
        end_time=end_time,
        first_message=first_message,
        message_count=message_count,
    )


def decode_project_path(encoded: str) -> str:
    """Convert encoded directory name back to a readable path.

    e.g. '-Users-david-Desktop-work' -> '/Users/david/Desktop/work'
    """
    decoded = "/" + encoded.lstrip("-").replace("-", "/")
    home = os.path.expanduser("~")
    if decoded == home:
        return "~"
    if decoded.startswith(home + "/"):
        return "~" + decoded[len(home):]
    return decoded


def discover_projects(base_dir: Path) -> list[ProjectInfo]:
    """Discover all project directories under the Claude projects dir."""
    projects = []
    if not base_dir.exists():
        return projects

    for entry in sorted(base_dir.iterdir()):
        if not entry.is_dir():
            continue
        sessions = list(entry.glob("*.jsonl"))
        if not sessions:
            continue
        projects.append(
            ProjectInfo(
                path=entry,
                display_name=decode_project_path(entry.name),
                session_count=len(sessions),
            )
        )
    return projects


def discover_sessions(project_dir: Path) -> list[Path]:
    """Find all JSONL session files in a project directory."""
    return sorted(
        project_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
