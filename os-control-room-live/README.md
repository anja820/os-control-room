# OS Control Room — LIVE (real process cockpit)

**CM-204 Operating Systems Capstone**

A terminal cockpit that manages **real Linux processes** — not a simulation.
Every row in its table is a real PID in `/proc`; every %CPU, memory figure and
state is read live from the kernel; every stop/continue/kill sends a **real
signal**; the deadlock is a **real file-lock deadlock** between real processes;
and CPU scheduling really changes with **`renice`**. The tool also **shows the
exact Linux command** behind each action and lets you run **any** Linux command
inline with `!` — so you are driving real Linux, live. It is impossible to
"click next" through this.

> This version was built specifically to address the feedback that a capstone
> must not behave like a *pre-recorded demo*. Nothing here is canned: the PIDs,
> CPU shares, memory and lock states are whatever the kernel is really doing.

---

## Why this is not a "click-next" demo

- **Real processes.** `spawn` fork/execs a real `worker.py`; it appears in `ps`,
  `top` and `/proc` with a real PID.
- **Real kernel data.** The table reads `/proc/<pid>/stat` and `status` — the
  same source `ps`/`top` use. Cross-check any row with `! ps` or `! top`.
- **Real signals.** `stop`/`cont`/`kill`/`term` send SIGSTOP/SIGCONT/SIGKILL/
  SIGTERM to real PIDs; you watch the state change in `/proc`.
- **Real deadlock.** Two real processes take real `flock` locks in opposite
  order and genuinely block in the kernel (`wchan = locks_lock_inode_wait`).
  `flock` has no kernel deadlock-detection, so it's a true deadlock the Control
  Room detects and you resolve with a real `kill`.
- **Real scheduling.** `contend` pins two CPU burners to one core; `nice` calls
  `renice`, and you watch the CPU share shift (e.g. 49/49 → 80/19). `policy`
  calls `chrt` to switch a process between the real SCHED_OTHER/FIFO/RR policies.
- **Real files.** `spawn file` opens real files and pipes and `fsync`s to disk;
  `files <pid>` lists its genuine descriptors straight from `/proc/<pid>/fd` —
  the same thing `lsof -p <pid>` reports.
- **Real paging.** `page <pid>` shows the kernel's own minor/major page-fault
  counters from `/proc/<pid>/stat`; watch minor faults climb as `spawn mem`
  touches new pages.
- **Your Linux skills, live.** `! <command>` runs anything — `ps`, `top`,
  `cat /proc/<pid>/status`, `kill -l`, `nproc`, `free -h`, `lsof`, `chrt -p` —
  right inside the tool.

---

## Showtime — the live experience

Real *and* fun to watch. All of it is driven by live `/proc` data — nothing is
an animation:

- **Mission-control boot sequence** — a block-letter `CONTROL ROOM` banner and
  real system checks (`/proc`, cores, `taskset`, `chrt`) before the prompt.
- **`live` dashboard** — the cockpit re-reads `/proc` every second until Ctrl-C:
  per-process **CPU bars**, **sparkline trends**, RSS, nice, state — all moving.
- **CPU core lanes** — one lane per core showing which core each worker is on
  *right now* (field 39 of `/proc/<pid>/stat`). Unpinned workers visibly hop
  between lanes; pinned ones can't.
- **Kernel news feed** — a live event ticker on the dashboard: every spawn,
  signal, renice, finish line and deadlock as it happens.
- **`race` — the Scheduler Grand Prix** ⭐ — two real processes pinned to ONE
  core race to a target; live progress bars; the **Linux scheduler alone picks
  the winner**. Sabotage mid-race: Ctrl-C out, `nice <pid> 19` or `stop <pid>`,
  then `race` to rejoin the broadcast. Block-letter `WINNER` podium at the end.
- **Deadlock red alert** — `graph` now sounds a full-width alarm bar and draws
  the two processes as boxes locked in a circle of arrows; killing the victim
  earns a green `DEADLOCK RESOLVED` banner.
- **`spawn zombie`** — a real zombie (state `Z`): a child that died but nobody
  `wait()`ed for. Signals can't kill what's already dead; kill the *parent* and
  watch init reap it.
- **SIGKILL goes BOOM** — plus an explanation of everything the kill just freed.
- **`web` — the wall display** — a self-contained browser dashboard (no
  frameworks, stdlib HTTP server) for a projector: live CPU line chart, meters,
  RSS bars, the event feed and a throbbing deadlock alarm. Read-only, fed by the
  same `/proc` data; the terminal stays mission control.

---

## Requirements

- A **Linux** machine/VM with Python 3 (needs `/proc`; won't run on Windows).
- Recommended for the scheduling demo: `taskset` + `renice` (util-linux):
  ```bash
  sudo apt install -y python3 util-linux procps
  ```

## Run

```bash
cd os-control-room-live
./run.sh            # or:  python3 oscr.py
```

---

## The two parts (kept short on purpose)

### Part 1 — Processes & Scheduling (real CPU, real renice, real chrt)
```text
spawn cpu           # a real CPU-burning process appears in the table
contend             # two CPU burners pinned to ONE core (so they compete)
watch               # live %CPU from /proc — both ~50%
nice <pid> 19       # renice one down; watch again — it drops, the other rises
policy <pid> rr 20  # switch a process to a REAL-TIME policy via chrt (privileged)
caps                # is real-time (rr/fifo) allowed on this machine? show why not
stop <pid>          # SIGSTOP: freeze it (state T); cont <pid> to resume
```
Verify independently any time: `! top`, `! ps -o pid,stat,ni,%cpu,comm`, or
`! chrt -p <pid>` (to confirm the scheduling policy really changed).

### Part 2 — Memory, Files & Deadlock (real resources)
Memory, open files and locks are all **real kernel resources a process holds**,
and the unifying idea is: **killing a process frees them all at once.**
```text
spawn mem 100       # a real process that allocates & touches 100 MB (watch RSS)
page <pid>          # real minor/major page faults from /proc/<pid>/stat
proc <pid>          # live /proc/<pid>: state, VmRSS, faults, sched policy, wchan
spawn file          # a real process that opens files/pipes and fsyncs to disk
files <pid>         # its REAL open file descriptors from /proc/<pid>/fd (like lsof)
deadlock            # two real processes deadlock on real file locks
graph               # wait-for cycle, built from what the processes really did
proc <pid>          # each one really blocked in the kernel (locks_lock_inode_wait)
kill <pid>          # SIGKILL a victim -> frees its lock AND memory; other unblocks
graph               # cycle gone: resolved for real
```

---

## Command reference (`help`)

**Part 1:** `spawn cpu`, `contend`, `race [millions]`, `live`, `watch [secs]`,
`nice <pid> <n>`, `policy <pid> <other|fifo|rr> [prio]`, `caps`, `stop <pid>`, `cont <pid>`
**Part 2:** `spawn mem <MB>`, `spawn file [path]`, `spawn zombie`, `page <pid>`,
`files <pid>`, `deadlock`, `graph`, `proc <pid>`, `kill <pid>`, `term <pid>`
**Anytime:** `! <command>` (run real Linux), `web [port]` (browser wall display),
`reveal on|off` (show/hide the Linux command behind each action), `ps`/Enter
(redraw), `help`, `exit`

Every managed action prints its real Linux equivalent (e.g. `kill -STOP 1234`,
`renice 19 -p 1234`), so the underlying Linux is always visible — and you can
type those raw commands yourself with `!` instead.

---

## How it maps to CM-204 topics

| Topic | Shown with REAL Linux |
|---|---|
| Processes & states | real PIDs; states R/S/D/T/Z read from `/proc/<pid>/stat` |
| CPU scheduling | `contend` + `renice`; live %CPU shift on a shared core |
| Scheduling policies | `policy` sets real SCHED_OTHER/FIFO/RR via `chrt` (field 41 in `/proc/<pid>/stat`) |
| Signals | real SIGSTOP/SIGCONT/SIGTERM/SIGKILL via `kill` |
| Memory | real RSS growth from a process that allocates & touches RAM |
| Paging & page faults | real minor/major fault counters from `/proc/<pid>/stat` (`page`) |
| Files & descriptors | real open fds from `/proc/<pid>/fd`; durable `fsync` writes (`spawn file`, `files`) |
| Concurrency & deadlock | real `flock` deadlock; wait-for graph; kill to resolve |
| The kernel underneath | `wchan`, `/proc/<pid>/status`, and `!` passthrough to `ps`/`top`/`lsof`/`chrt` |

---

## Files

```
os-control-room-live/
├── run.sh          # launcher
├── oscr.py         # the Control Room: manages real processes, REPL, dashboard
├── worker.py       # the REAL worker process (cpu / mem / io / file / lock / race / zombie)
├── procinfo.py     # reads real data from /proc (state, RSS, %CPU, faults, policy, fds, wchan, core)
├── ui.py           # colour / panels / tables / bars / sparklines (presentation only)
├── webdash.py      # optional browser wall-display (stdlib HTTP server, no frameworks)
└── README.md
```

**Design:** the Control Room never fabricates data — `procinfo.py` reads the
kernel's own `/proc` files, and `worker.py` does real work (spins the CPU,
touches real pages, holds real `flock` locks). Because everything is real, the
demo can't be scripted: the professor can interrupt at any point and ask you to
`spawn`, `kill`, `renice`, or `! cat /proc/<pid>/status` something new.

*(This live version is the project. It began as a pure simulator, which was then
rebuilt to control real Linux processes — the version you see here.)*
