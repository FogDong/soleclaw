# Commands

All commands accept `--config / -c` to specify a custom config file path. Default: `~/.soleclaw/config.json`.

## Core Commands

### `soleclaw configure`

Interactive configuration wizard. Sets up model selection, Telegram channel, and bootstraps the workspace on first run.

```bash
soleclaw configure
soleclaw configure -w /path/to/workspace
```

### `soleclaw agent`

Chat with the agent. Without arguments, starts an interactive REPL. With an argument, runs a single exchange and exits.

```bash
soleclaw agent            # interactive mode
soleclaw agent "hello"    # one-shot mode
```

If no config exists, automatically runs `configure` first.

### `soleclaw status`

Show runtime and configuration status: workspace path, model, gateway state, channel config, and identity setup.

```bash
soleclaw status
```

## Gateway

The gateway connects channels (Telegram, etc.) to the agent and runs cron jobs in the background.

### `soleclaw gateway start`

Start the gateway. Runs in the background by default.

```bash
soleclaw gateway start              # background (daemon)
soleclaw gateway start --foreground  # foreground with logs to stdout
```

### `soleclaw gateway stop`

Stop the running gateway.

```bash
soleclaw gateway stop
```

### `soleclaw gateway restart`

Restart the gateway (stop + start).

```bash
soleclaw gateway restart
```

## Session

Manage conversation sessions. The agent maintains separate sessions per channel/chat (e.g. `telegram:12345`, `cli`).

### `soleclaw session list`

List all active sessions and their SDK session IDs.

```bash
soleclaw session list
```

### `soleclaw session clear`

Clear conversation history. Without arguments, clears all sessions. With a session key, clears only that session.

```bash
soleclaw session clear                       # clear all
soleclaw session clear telegram:12345        # clear specific session
```

## Prompt

View and edit the files that compose the agent's system prompt.

### `soleclaw prompt show`

Print the fully assembled system prompt (what the agent actually sees).

```bash
soleclaw prompt show
```

### `soleclaw prompt files`

List all files that compose the system prompt and their status: workspace files, always-on skills, and tool library entries.

```bash
soleclaw prompt files
```

### `soleclaw prompt edit <file>`

Open a system prompt file in `$EDITOR`. Supports shorthand aliases:

| Alias | File |
|-------|------|
| `soul` | SOUL.md |
| `identity` | IDENTITY.md |
| `user` | USER.md |
| `agents` | AGENTS.md |
| `tools` | TOOLS.md |
| `memory` | MEMORY.md |
| `bootstrap` | BOOTSTRAP.md |

```bash
soleclaw prompt edit soul       # opens SOUL.md
soleclaw prompt edit agents     # opens AGENTS.md
soleclaw prompt edit TOOLS.md   # full filename also works
```

### `soleclaw prompt diff`

Show diff between current workspace files and their bootstrap templates. Useful for seeing what the agent (or you) has changed.

```bash
soleclaw prompt diff          # diff all files
soleclaw prompt diff user     # diff only USER.md
```
