# Claude Code Session Viewer

A terminal UI for browsing and reading previous Claude Code session transcripts — similar to how they looked during the original session.

Built with Python and [Textual](https://textual.textualize.io/).

## Features

- Three-panel layout: Projects | Sessions | Conversation
- Automatically discovers sessions from `~/.claude/projects/`
- Shows session start and end times with first message preview
- Color-coded messages: user (green), assistant (purple), tool calls (orange)
- Collapsible tool call details with input and output
- Keyboard-driven navigation

## Install

```bash
git clone https://github.com/dsaccon/coding-agent-session-viewer.git
cd coding-agent-session-viewer
uv venv && uv pip install -e .
```

## Usage

```bash
claude-sessions
```

Or run directly:

```bash
uv run python -m claude_session_viewer
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `←` / `→` | Switch between panels |
| `↑` / `↓` | Navigate within a panel |
| `Tab` / `Shift+Tab` | Switch between panels |
| `Enter` | Select item / expand tool call |
| `Escape` | Go back to previous panel |
| `q` | Quit |

## Development

```bash
uv venv && uv pip install -e .
uv pip install pytest
uv run pytest tests/ -v
```

## How It Works

Claude Code stores session transcripts as JSONL files under `~/.claude/projects/`. Each subdirectory represents a project, and each `.jsonl` file within is a session. The viewer parses these files and renders them in a navigable terminal interface.
