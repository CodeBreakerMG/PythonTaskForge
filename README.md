# TaskForge

**A local Python automation runtime for macOS**

Version **1.0**

TaskForge runs scheduled jobs in the background, keeps history in SQLite, and gives you a desktop dashboard to manage everything — without creating dozens of LaunchAgents.

Think of it as a lightweight mix of Task Scheduler, cron, and a local Zapier — focused on your machine.

```text
launchd (optional, starts once at login)
        │
        ▼
 TaskForge Runtime
 ├── Scheduler
 ├── Registry
 ├── Executor
 ├── SQLite database
 └── Notifications
        │
        ▼
 Desktop Dashboard (+ menu bar tray)
```

---

## Why TaskForge?

Instead of maintaining many `launchd` plists:

```text
launchd
└── one TaskForge agent
      └── manages all tasks internally
```

You get:

- One place to create, edit, enable, and run tasks
- Human-friendly schedules (`daily 6:00PM`, `mondays and thursdays at 4 PM`)
- Execution history and logs
- Background mode (close the window, runtime keeps going)
- macOS notifications when jobs finish or fail

---

## Features (v1.0)

| Area | What you get |
|------|----------------|
| **Tasks** | Run Python scripts or shell commands |
| **Scheduling** | Manual, daily, weekly, one-time / multi-date |
| **Dashboard** | Create, modify, run, enable/disable, delete |
| **History** | Recent runs with status, duration, and output |
| **Tray** | Close window → stays in menu bar; Dock click reopens |
| **Notifications** | macOS alerts on success / failure |
| **Storage** | Local SQLite DB (`database/taskforge.db`, gitignored) |

---

## Requirements

- macOS (GUI + tray + notifications tested here)
- Python **3.9+**
- Project dependencies from `requirements.txt`

Stack: **PySide6**, **APScheduler**, **SQLAlchemy/SQLite**, **loguru**

---

## Quick start

```bash
cd /path/to/PythonTaskForge

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python app.py
```

First launch seeds a sample task: **Hello TaskForge** (`tasks/hello.py`).

### CLI helpers

```bash
python app.py --list
python app.py --run "Hello TaskForge"
```

---

## Creating a task

In the dashboard, click **Create Task**:

| Field | Meaning | Example |
|-------|---------|---------|
| **Name** | Unique label | `Agenda Report` |
| **Action** | How to run it | `script` or `command` |
| **Target** | What to run | see below |
| **Schedule** | When to run | `manual`, `daily 6:00PM`, … |
| **Enabled** | Whether scheduler may fire it | checked / unchecked |

### Action + Target

**Script** — Target is the `.py` path only (do **not** include `python3`):

```text
Action:  script
Target:  /Users/you/Projects/mytool/report_generator.py
```

or a project-relative path:

```text
Target:  tasks/hello.py
```

**Command** — Target is a full shell command:

```text
Action:  command
Target:  df -h
```

### Schedule examples

| String | Meaning |
|--------|---------|
| `manual` | Only when you click Run |
| `daily 6:00PM` | Every day at 18:00 |
| `daily 18:00` | Same, 24-hour time |
| `mondays and thursdays at 4 PM` | Weekly on those days |
| `monday, friday at 9:30AM` | Weekly on those days |
| `3/31/2026 at 4 PM` | One specific date |
| `3/31/2026 and 4/15/2026 at 4 PM` | Multiple dates, same time |

---

## Background mode

- Click the window **X** → dashboard hides; runtime **keeps running**
- Reopen from the **Dock** icon or the menu-bar **TF** icon → **Open Dashboard**
- Fully exit with tray menu → **Quit TaskForge**

---

## Optional: start at login with launchd

TaskForge is designed so **launchd only starts the app once**. Create:

`~/Library/LaunchAgents/com.taskforge.runtime.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.taskforge.runtime</string>

  <key>ProgramArguments</key>
  <array>
    <string>/ABSOLUTE/PATH/TO/PythonTaskForge/.venv/bin/python</string>
    <string>/ABSOLUTE/PATH/TO/PythonTaskForge/app.py</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/ABSOLUTE/PATH/TO/PythonTaskForge</string>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>/ABSOLUTE/PATH/TO/PythonTaskForge/logs/launchd.out.log</string>

  <key>StandardErrorPath</key>
  <string>/ABSOLUTE/PATH/TO/PythonTaskForge/logs/launchd.err.log</string>
</dict>
</plist>
```

Load it:

```bash
mkdir -p /ABSOLUTE/PATH/TO/PythonTaskForge/logs
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taskforge.runtime.plist
launchctl kickstart -k gui/$(id -u)/com.taskforge.runtime
```

Unload:

```bash
launchctl bootout gui/$(id -u)/com.taskforge.runtime
```

> With `KeepAlive` enabled, quitting from the tray may relaunch the app. Unload the agent to stop it fully.

---

## Project structure

```text
PythonTaskForge/
├── app.py                 # Entrypoint (GUI + CLI)
├── requirements.txt
├── runtime/
│   ├── task.py            # Task model + schedule parser
│   ├── registry.py        # In-memory registry ↔ SQLite
│   ├── executor.py        # Runs scripts / commands
│   ├── scheduler.py       # APScheduler wiring
│   ├── service.py         # Runtime orchestration
│   └── notifications.py   # macOS + tray notifications
├── database/
│   ├── models.py          # SQLAlchemy models
│   ├── database.py        # Engine / sessions
│   └── taskforge.db       # Created at runtime (gitignored)
├── gui/
│   ├── main_window.py     # Dashboard
│   ├── task_editor.py     # Create / modify dialog
│   └── tray.py            # Menu-bar tray
├── tasks/
│   └── hello.py           # Sample script
└── logs/                  # App + launchd logs (gitignored)
```

---

## Data & privacy

- Task definitions, history, and logs live in **`database/taskforge.db`**
- That file is **gitignored** — it may contain paths and command output from your machine
- Runtime logs go under **`logs/`** (also gitignored)

---

## Roadmap

**Done in v1.0**

- Runtime, scheduler, SQLite, dashboard, tray, notifications

**Next ideas**

- Start hidden / `--background` mode for launchd
- Plugin system
- Folder / file watchers and richer event triggers
- Visual task builder
- Retry policies, dependencies, export/import

---

## License

See [LICENSE](LICENSE).
