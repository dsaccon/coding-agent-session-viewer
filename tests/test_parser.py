import os
import tempfile
from pathlib import Path

from claude_session_viewer.parser import (
    Message,
    ProjectInfo,
    SessionData,
    SessionSummary,
    ToolCall,
    ToolResult,
    decode_project_path,
    discover_projects,
    discover_sessions,
    load_session_summary,
    parse_session,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_session.jsonl"


# --- parse_session tests ---


def test_parse_session_returns_session_data():
    session = parse_session(FIXTURE)
    assert isinstance(session, SessionData)
    assert session.session_id == "sample_session"


def test_parse_session_extracts_timestamps():
    session = parse_session(FIXTURE)
    assert session.start_time is not None
    assert session.end_time is not None
    assert session.end_time >= session.start_time


def test_parse_session_extracts_first_user_message():
    session = parse_session(FIXTURE)
    assert session.first_message == "Show me the files in this directory"


def test_parse_session_filters_non_conversation_messages():
    session = parse_session(FIXTURE)
    types = {m.type for m in session.messages}
    assert "progress" not in types
    assert "user" in types
    assert "assistant" in types


def test_parse_session_message_count():
    session = parse_session(FIXTURE)
    # 2 user + 3 assistant = 5 conversation messages (progress filtered)
    assert len(session.messages) == 5


def test_message_content_extraction():
    session = parse_session(FIXTURE)
    user_msg = session.messages[0]
    assert user_msg.role == "user"
    assert user_msg.text == "Show me the files in this directory"


def test_tool_use_extraction():
    session = parse_session(FIXTURE)
    tool_msg = session.messages[2]
    assert tool_msg.role == "assistant"
    assert len(tool_msg.tool_calls) == 1
    assert tool_msg.tool_calls[0].name == "Bash"
    assert tool_msg.tool_calls[0].input == {"command": "ls -la"}


def test_tool_result_extraction():
    session = parse_session(FIXTURE)
    result_msg = session.messages[3]
    assert result_msg.role == "user"
    assert len(result_msg.tool_results) == 1
    assert "file1.txt" in result_msg.tool_results[0].content


# --- load_session_summary tests ---


def test_load_session_summary():
    summary = load_session_summary(FIXTURE)
    assert summary.session_id == "sample_session"
    assert summary.first_message == "Show me the files in this directory"
    assert summary.start_time is not None
    assert summary.end_time is not None
    assert summary.message_count > 0


def test_load_session_summary_timestamps():
    summary = load_session_summary(FIXTURE)
    assert summary.start_time.hour == 10
    assert summary.start_time.minute == 0
    assert summary.end_time.minute == 3


# --- decode_project_path tests ---


def test_decode_project_path_simple():
    # Use a path that won't be the current user's home
    assert decode_project_path("-var-log") == "/var/log"


def test_decode_project_path_long():
    encoded = "-var-lib-data-projects-misc"
    assert decode_project_path(encoded) == "/var/lib/data/projects/misc"


def test_decode_project_path_collapses_home():
    home = os.path.expanduser("~")
    encoded = home.replace("/", "-")
    result = decode_project_path(encoded)
    assert result == "~"


# --- discover_projects tests ---


def test_discover_projects_with_temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj1 = Path(tmpdir) / "-Users-test-project1"
        proj1.mkdir()
        (proj1 / "session1.jsonl").write_text("")
        (proj1 / "session2.jsonl").write_text("")

        proj2 = Path(tmpdir) / "-Users-test-project2"
        proj2.mkdir()
        (proj2 / "session1.jsonl").write_text("")

        projects = discover_projects(Path(tmpdir))
        assert len(projects) == 2
        names = {p.display_name for p in projects}
        assert "/Users/test/project1" in names
        assert "/Users/test/project2" in names


def test_discover_projects_ignores_non_directories():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "some-file.txt").write_text("not a dir")
        proj = Path(tmpdir) / "-Users-test"
        proj.mkdir()
        (proj / "s.jsonl").write_text("")

        projects = discover_projects(Path(tmpdir))
        assert len(projects) == 1


# --- discover_sessions tests ---


def test_discover_sessions_returns_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj = Path(tmpdir) / "-Users-test"
        proj.mkdir()
        (proj / "abc-123.jsonl").write_text("")
        (proj / "def-456.jsonl").write_text("")
        (proj / "not-a-session.txt").write_text("")

        sessions = discover_sessions(proj)
        assert len(sessions) == 2
        assert all(s.suffix == ".jsonl" for s in sessions)
