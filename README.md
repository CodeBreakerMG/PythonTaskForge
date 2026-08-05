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

## Install as a macOS app (optional)

You can keep using `python app.py`, or package TaskForge as a normal double-clickable Mac app.

### 1. Build `TaskForge.app`

```bash
cd /path/to/PythonTaskForge
source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller

pyinstaller \
  --name TaskForge \
  --windowed \
  --noconfirm \
  --clean \
  --osx-bundle-identifier com.taskforge.runtime \
  --add-data "tasks:tasks" \
  app.py
```

This creates:

```text
dist/TaskForge.app
```

Open it once to verify:

```bash
open dist/TaskForge.app
```

### 2. Install the app

Copy it into Applications:

```bash
cp -R dist/TaskForge.app /Applications/
```

Then open it from Finder, Spotlight, or:

```bash
open /Applications/TaskForge.app
```

> Building the `.app` does **not** register launchd by itself. Autostart is a separate step below.

### 3. Start at login with launchd (optional)

TaskForge is designed so **one LaunchAgent** starts the app at login; TaskForge manages all tasks internally.

After `TaskForge.app` is installed:

```bash
cd /path/to/PythonTaskForge
./scripts/install_launchd.sh
```

Or pass the app path explicitly:

```bash
./scripts/install_launchd.sh /Applications/TaskForge.app
```

What the script does:

1. Finds `TaskForge.app` (`/Applications`, `~/Applications`, or `dist/`)
2. Writes `~/Library/LaunchAgents/com.taskforge.runtime.plist`
3. Loads the agent with `launchctl` (`RunAtLoad` + `KeepAlive`)
4. Writes logs to `~/Library/Logs/TaskForge/`

Check that it loaded:

```bash
launchctl print gui/$(id -u)/com.taskforge.runtime | head -40
```

### 4. Uninstall the login agent

```bash
./scripts/install_launchd.sh --uninstall
```

> With `KeepAlive` enabled, quitting from the tray may relaunch TaskForge. Use `--uninstall` to stop autostart fully.

### Notes

- First launch from an unsigned build may require **right-click → Open** (Gatekeeper)
- Database location is configurable in the app under **Settings** (recommended for packaged use)
- Prefer the `.app` + launchd script for daily use; use `python app.py` while developing

---

## Project structure

```text
PythonTaskForge/
├── app.py                 # Entrypoint (GUI + CLI)
├── requirements.txt
├── scripts/
│   └── install_launchd.sh # Register / unregister login LaunchAgent
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
├── config/
│   └── settings.py        # DB path + app preferences
├── gui/
│   ├── main_window.py     # Dashboard
│   ├── task_editor.py     # Create / modify dialog
│   ├── settings_dialog.py # Database location settings
│   └── tray.py            # Menu-bar tray
├── tasks/
│   └── hello.py           # Sample script
└── logs/                  # App logs (gitignored)
```

---

## Data & privacy

- The SQLite database path is **configurable** in the app: **Settings → Database file**
- Preference file: `~/Library/Application Support/TaskForge/settings.json`
- Default DB:
  - existing project file `database/taskforge.db` if present (backward compatible)
  - otherwise `~/Library/Application Support/TaskForge/taskforge.db`
- Changing the path opens/creates that file; the old DB is left as-is
- Runtime logs go under **`logs/`** (gitignored)

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
