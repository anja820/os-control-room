# OS Control Room — Presentation Guide

**CM-204 Capstone · "OS Control Room: a live cockpit over REAL Linux processes"**

This is your cheat-sheet for demoing the project live on your Linux VM. It has
the exact commands to run, what to say at each step, and the real Linux tools to
cross-check every claim with.

**This project is not a simulation.** `os-control-room-live` manages **real Linux
processes**: every PID, %CPU, memory figure, page fault, file descriptor,
scheduling policy and lock is read straight from `/proc` or set with a real
command (`renice`, `chrt`, `kill`, `flock`). The tool also **prints the exact
Linux command behind every action**, and lets you run any command inline with
`!` — so you are driving the real kernel, live.

> **Why this matters:** the assignment warned against "click-next" demos. This
> tool *cannot* be scripted — the numbers are whatever the machine is really
> doing this second, and PIDs differ every run. The professor can interrupt at
> any moment ("now kill that one", "show me its /proc") and you can, because it
> is all real.

---

## 0. Before the presentation — get the project onto the VM

Copy the `OS-Capstone` folder into your Linux VM. Any of these works:

- **VirtualBox shared folder** (Devices → Shared Folders), then in the VM:
  ```bash
  cp -r /media/sf_OS-Capstone ~/OS-Capstone
  ```
- **scp** from another machine: `scp -r OS-Capstone user@vm:~/`
- A USB stick or a `git clone` if you push it to a repo.

Then make sure the tools are present (one-time):

```bash
python3 --version                               # needs Python 3 (usually present)
sudo apt install -y python3 util-linux procps   # renice, taskset, chrt, ps, top, free, vmstat
```

> **Do a full dry-run the day before.** Launch it and click through every demo
> once so nothing surprises you on stage. Open a **second terminal** too — that's
> where you cross-check with raw `ps`/`top`/`lsof`/`chrt`.

---

## 1. Opening — prove it's real (~1 min)

```bash
cd ~/OS-Capstone/os-control-room-live
./run.sh          # or:  python3 oscr.py
```

Press Enter at the welcome screen. Point out the **live process table** — every
row is a real PID read from `/proc`, the same source `ps` and `top` use.

Say: *"This isn't a simulation. Every process you'll see is a real Linux process
I spawn, watched live through /proc. I'll manage them with real signals and real
scheduling. Please interrupt me and ask me to do something to any of them."*

Then prove it immediately:

```
spawn cpu
```

A real process appears with a real PID. Flip to the **second terminal**:

```bash
ps -o pid,stat,%cpu,comm -C python3     # same PID, really burning CPU
```

> `reveal` is **on** by default, so the tool prints the exact command behind
> every action. Say: *"watch the `$` line — that's the real command I just ran."*

Type `help` for the full command menu; press Enter any time to redraw the table.

---

## 2. The live demos

Run in any order. Each uses a PID from the table — read it off the screen.

### DEMO A — Real processes & CPU scheduling

```
contend           # two CPU burners pinned to ONE core, so they must share it
watch             # live %CPU from /proc — both settle around ~50%
nice <pid> 19     # renice one down; watch again — it drops, the other rises
stop <pid>        # SIGSTOP: freeze it (state T)
cont <pid>        # SIGCONT: resume it
```

*"Same core, two processes — the scheduler splits it ~50/50. I renice one and
the split shifts, live. Then stop/cont send real SIGSTOP/SIGCONT."*
**Cross-check (2nd terminal):** `top`, or `ps -o pid,ni,%cpu,psr,comm -C python3`.

### DEMO B — Scheduling *policies*, not just priority ⭐

```
proc <pid>              # note: sched = OTHER (CFS, normal)
policy <pid> rr 20      # switch to a REAL real-time Round-Robin policy (chrt)
proc <pid>              # sched now = RR (real-time)
```

Talking point: *"`nice` only re-weights a process **inside** the normal
scheduler. `policy` switches **which scheduler** the kernel uses at all — I just
moved it onto a real-time policy with `chrt`, and `/proc` confirms it."*
**Cross-check:** `chrt -p <pid>` shows the same policy.

> Real-time policies are privileged. On many lab machines they're refused **even
> with `sudo`** (an unprivileged container drops `CAP_SYS_NICE`, or real-time
> bandwidth is disabled). Don't fight it — turn it into a lesson: type **`caps`**
> to *show* exactly why the kernel blocks RR/FIFO here, then demo `policy <pid>
> other` (always works) and shift CPU share with `nice`. If the tool says sudo
> *might* help, it'll print the `! sudo chrt …` line to try.

### DEMO C — Real memory & page faults

```
spawn mem 200     # a process that allocates AND touches 200 MB (real RSS)
page <pid>        # real minor/major page-fault counters from /proc
watch             # watch RSS climb as it touches every page
```

*"Asking for memory and **using** it differ — Linux only backs a page with RAM
when the process touches it. Each touch of a fresh page is a **minor page
fault**, and you can watch that counter climb."*
**Cross-check:** `vmstat 1 3` (system-wide paging), `free -h` (RAM used/free).

### DEMO D — Real files & descriptors

```
spawn file        # a process that opens a file + a pipe and fsyncs to disk
files <pid>       # its REAL open file descriptors, straight from /proc/<pid>/fd
```

You'll see `fd 0/1/2` (stdin/out/err), a **regular file** (fd 3) and a **pipe**
(fds 4/5). *"This is the kernel's per-process file table. Each `fsync` forces the
bytes to disk — the real, expensive 'commit' a database or a filesystem journal
pays for durability."*
**Cross-check:** `lsof -p <pid>`, or `ls -l /proc/<pid>/fd`.

### DEMO A½ — The Scheduler Grand Prix ⭐ (the crowd-pleaser)

```
race              # two real processes race to 50M iterations on ONE core
                  # live progress bars — the Linux scheduler picks the winner
Ctrl-C            # leave the broadcast (the racers keep running!)
nice <pid> 19     # sabotage one racer — a real renice
race              # rejoin the broadcast — watch it fall behind and lose
```

*"Both racers burn real CPU on the same core. Nobody scripted a winner — the
kernel's scheduler decides. Now I'll handicap one with a real `renice` and you
can watch it lose."* You can also `stop <pid>` a racer (it freezes on the track)
and `cont <pid>` it later. The `WINNER` podium at the end is decided by Linux.
**Cross-check:** `top` in the 2nd terminal — the two racers' CPU shares match
the bars.

### The always-on cockpit

Type `live` at any point for the full mission-control dashboard — CPU bars,
sparkline trends, **core lanes** (watch unpinned workers hop between cores),
and the kernel-news event feed — updating every second until Ctrl-C.

### DEMO E — Real deadlock, then resolve it (the flagship)

```
deadlock          # two real processes take real flock locks in opposite order
graph             # RED ALERT: alarm bar + the two processes drawn as boxes
                  # locked in a circle of arrows (the wait-for cycle)
proc <pid>        # each is truly blocked in the kernel: wchan = locks_lock_inode_wait
kill <pid>        # SIGKILL a victim → BOOM → frees its lock AND its memory
graph             # green DEADLOCK RESOLVED banner — the survivor unblocked
```

Talking point (the thesis): *"A process holds real resources — memory, open
files, locks. One `kill` frees them **all** at once, which is why killing a
deadlocked process both reclaims its memory and instantly unblocks whoever was
waiting on its lock. `flock` has no auto-recovery, so this is a genuine stuck
state that **I** break."*
**Cross-check:** `cat /proc/locks` shows the real kernel locks.

### DEMO F — Zombies (30 seconds of fun)

```
spawn zombie      # a child dies, its parent refuses to wait() for it
                  # → a REAL zombie, state Z in the table
kill <zombie-pid> # nothing happens — you can't kill what's already dead!
kill <parent-pid> # kill the PARENT → init adopts and reaps the zombie
```

*"A zombie isn't a running process — it's an exit status nobody collected."*
**Cross-check:** `ps -o pid,stat,comm` shows the `Z` / `<defunct>` entry.

### The wall display (optional, big-screen wow)

```
web               # starts a browser dashboard on port 8000
```

Open `http://localhost:8000` (or the printed VM address) on the projector: live
CPU line chart, meters, RSS bars, the event feed, and a throbbing red banner
when a deadlock exists. It's read-only and fed by the same `/proc` reads — you
keep driving from the terminal. *"The browser is just a window; mission control
stays right here."*

---

## 3. Cross-check card (second terminal)

Every live panel maps one-to-one onto a standard tool — run these to prove it:

| Live tool shows | Verify with |
|---|---|
| process table / states | `ps -el`, `top` |
| CPU share on a core | `top`, `ps -o pid,%cpu,comm` |
| scheduling policy (`policy`) | `chrt -p <pid>` |
| RSS + page faults (`page`) | `free -h`, `vmstat 1 3` |
| open descriptors (`files`) | `lsof -p <pid>`, `ls -l /proc/<pid>/fd` |
| the deadlock's locks | `cat /proc/locks` |
| every signal it sends | `kill -l` |

---

## 4. In-app command reference

| Command | Does |
|---|---|
| `spawn cpu` | fork+exec a real CPU-burning process |
| `spawn mem <MB>` | a real process that allocates & touches `<MB>` of RAM |
| `spawn file [path]` | a real process that opens files/pipes and fsyncs to disk |
| `spawn io` | a real process that blocks (sleeping `S` state) |
| `spawn zombie` | a real zombie: dead child, parent won't reap it (state `Z`) |
| `contend` | two CPU burners pinned to ONE core (scheduling demo) |
| `race [millions]` | Scheduler Grand Prix: two racers, one core, kernel picks the winner |
| `live` | full mission-control dashboard until Ctrl-C (bars, lanes, news feed) |
| `watch [secs]` | live-monitor real %CPU from /proc |
| `web [port]` | browser wall-display of the same /proc data (projector) |
| `nice <pid> <n>` | renice (higher n = lower priority = less CPU) |
| `policy <pid> <other\|fifo\|rr> [prio]` | set the real scheduler policy via `chrt` |
| `caps` | show whether this machine allows real-time (rr/fifo) scheduling, and why not |
| `stop` / `cont` / `term` / `kill <pid>` | SIGSTOP / SIGCONT / SIGTERM / SIGKILL |
| `proc <pid>` | live `/proc/<pid>`: state, RSS, faults, policy, wchan |
| `page <pid>` | real minor/major page faults + RSS |
| `files <pid>` | real open file descriptors from `/proc/<pid>/fd` |
| `deadlock` / `graph` | real flock deadlock / wait-for graph + cycle detection |
| `! <command>` | run ANY real Linux command inline |
| `reveal on\|off` | show/hide the real command behind each action (on by default) |
| `help` / `exit` | help / quit (auto-cleans up every spawned process) |

---

## 5. Show the code behind a feature (if asked)

Judges often ask "show me where X happens." These land instantly:

```bash
cd ~/OS-Capstone/os-control-room-live

# Reading real kernel data from /proc (state, RSS, faults, policy, fds, wchan)
grep -n "def read_stat\|def list_fds\|minflt\|policy\|VmRSS\|wchan" procinfo.py

# The real worker: what each mode actually does on the OS
grep -n "def do_cpu\|def do_mem\|def do_file\|def do_lock\|flock\|fsync" worker.py

# Real actions: signals, renice, chrt, the flock deadlock detection
grep -n "os.kill\|setpriority\|chrt\|def deadlock\|def graph\|def show_fds" oscr.py
```

*"`procinfo.py` only ever reads the kernel's own `/proc` files — it never invents
a number. `worker.py` does real work (spins the CPU, touches real pages, holds
real `flock` locks, `fsync`s to disk). `ui.py` is pure presentation. That clean
split is why nothing here can be faked."*

---

## 6. Two-minute talking script (the "why")

> "Operating systems are usually taught as separate topics — scheduling, memory,
> files, locks, signals. In a real system they constantly affect each other. I
> built a control room where I play the OS operator over **real** Linux
> processes: I spawn them, watch them live through /proc, share the CPU with real
> scheduling and real-time policies, watch real memory and page faults, inspect
> real open file descriptors, and cause then fix a **real** deadlock. Every
> action maps one-to-one onto the tools the professor would type — `ps`, `top`,
> `free`, `vmstat`, `lsof`, `chrt`, `kill`. Nothing is pre-recorded, so it turns
> the invisible decisions of an OS into something you can see and drive live."

---

## 7. Likely questions — quick answers

- **"Is it really live?"** Yes — cross-check any PID in `top`/`ps`. PIDs differ
  every run, so it can't be scripted. Give me a process to act on.
- **"What's your role?"** I'm the OS operator. The tool reads `/proc` and runs
  the exact commands I choose; I decide what happens to each process.
- **"Real deadlock?"** Two real `flock` locks taken in opposite order; both
  processes block in `locks_lock_inode_wait`. `flock` has no kernel
  auto-detection, so it's a genuine stuck state I break with a real `kill`.
- **"nice vs policy?"** `nice` re-weights within the normal (CFS) scheduler;
  `policy` uses `chrt` to switch the scheduling policy entirely (SCHED_OTHER →
  real-time FIFO/RR).
- **"Why combine memory + locks + files?"** They're all resources a process
  holds — one `kill` frees them all at once.
- **"What would you add next?"** Real cgroup CPU/memory limits, or a real-time
  latency measurement under RR vs OTHER.

---

## 8. Emergency fallbacks

- **Colours look like garbage?** `exit`, then `NO_COLOR=1 ./run.sh`.
- **`taskset`/`renice`/`chrt` missing?** `sudo apt install -y util-linux`.
- **CPU% shows `—`?** Run `watch` (it needs two samples a second apart) or press
  Enter to redraw.
- **renice "permission denied"?** Only *negative* nice needs sudo; use 1–19.
- **`policy fifo/rr` refused (even with `sudo`)?** Expected on locked-down lab
  machines — real-time scheduling is a privileged operation the environment
  blocks for everyone. Type `caps` to show *why* (CAP_SYS_NICE / RT bandwidth),
  then demo `policy <pid> other` (always works). Only try `! sudo chrt …` if
  `caps`/the tool says root might help.
- **A worker won't die?** `kill <pid>` (SIGKILL) always works; on `exit` the tool
  cleans up everything it spawned.
- **Lost track mid-demo?** Type `ps` (or press Enter) to redraw the real table.

**Everything is real — if in doubt, prove it with `! ps`, `! top`, or `! lsof`.**
