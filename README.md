# Claude Code Session Viewer

A terminal UI for browsing and reading previous Claude Code session transcripts — similar to how they looked during the original session.

Built with Python and [Textual](https://textual.textualize.io/).

![Demo](demo.gif)

## Key Features

- **Three-panel layout** — Projects | Sessions | Conversation, with keyboard-driven navigation
- **Inline diff view** — File edits shown with red/green coloring, just like Claude Code
- **Markdown rendering** — Plans and assistant messages render with proper formatting (headers, code blocks, lists)
- **Select and copy** — Enter select mode to pick conversation blocks and copy them to your clipboard
- **Session ID copy** — Copy the session ID to clipboard for resuming sessions with `claude --resume`
- **Fast navigation** — Debounced loading and session caching for snappy browsing
- **Color-coded messages** — User (green), assistant (purple), tool calls (orange)
- **Works over SSH** — Clipboard copy uses both native tools and OSC 52 for remote sessions

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

### Navigation

| Key | Action |
|-----|--------|
| `←` / `→` | Switch between panels |
| `↑` / `↓` / `j` / `k` | Navigate within a panel |
| `Tab` / `Shift+Tab` | Switch between panels |
| `Enter` | Select item |
| `Escape` | Go back to previous panel |
| `PgUp` / `PgDn` | Page up/down in conversation |
| `Home` / `End` | Jump to top/bottom of conversation |
| `q` | Quit |

### Clipboard

| Key | Action |
|-----|--------|
| `c` | Copy session ID to clipboard |
| `s` | Enter select mode (in conversation panel) |

### Select Mode

Press `s` in the conversation panel to enter select mode, then:

| Key | Action |
|-----|--------|
| `↑` / `↓` / `j` / `k` | Move cursor between message blocks |
| `Space` | Toggle selection on current block |
| `a` | Select / deselect all |
| `y` / `Enter` | Copy selected blocks to clipboard |
| `Escape` | Exit select mode |

## Development

```bash
uv venv && uv pip install -e .
uv pip install pytest
uv run pytest tests/ -v
```

## How It Works

Claude Code stores session transcripts as JSONL files under `~/.claude/projects/`. Each subdirectory represents a project, and each `.jsonl` file within is a session. The viewer parses these files and renders them in a navigable terminal interface.
