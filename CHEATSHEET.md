# 🖥️ OS Control Room (LIVE) — Presentation Cheatsheet

**Real Linux processes. Nothing pre-recorded.** Keep this on your phone. Type the
**bold** commands; the line under each says *what happens* and *what to say*.

> **Why this matters:** your professor warned against "click-next" demos. This
> tool controls **real processes** — real PIDs, real %CPU, real memory, real
> signals, a real deadlock. He can interrupt you at any moment and say "now kill
> that one" or "show me its /proc" — and you can, because it's all real.

---

## ⚙️ SETUP (before class)

```bash
cd os-control-room-live
sudo apt install -y python3 util-linux procps   # if needed (taskset, renice, chrt, ps, lsof)
./run.sh          # opens the live cockpit
```
Test once: type `spawn cpu`, then `! top` — your worker is really there. `exit`.

**Open a SECOND terminal too** — you'll flip to it to prove things with raw
Linux (`top`, `ps`, `cat /proc/<pid>/status`). That second terminal is your
"I know Linux" moment.

---

## 🎬 OPENING (say this)

> "This isn't a simulation. Every process you'll see is a real Linux process I
> spawn, watched live through /proc — the same place `ps` and `top` read. I'll
> manage them with real signals and real scheduling. Please interrupt me and ask
> me to do something to any of them."

Type: **`spawn cpu`** → *"There's a real process. Let me prove it —"* → in the
2nd terminal: **`ps -o pid,stat,%cpu,comm -C python3`** (or `top`). Same PID.

---

## 🕐 PART 1 — Processes & Scheduling (real CPU) — ~3 min

| # | Type this | What happens / what to say |
|---|-----------|----------------------------|
| 1 | `contend` | Spawns **two** CPU burners **pinned to one core** so they truly compete. |
| 2 | `watch` | Live %CPU from /proc: both **~50%** — the scheduler shares the core. |
| 3 | `nice <pidB> 19` | *"I'll lower one's priority — a real `renice`."* (Use a PID from the table.) |
| 4 | `watch` | Now **~80% / ~19%** — you SEE the Linux scheduler react. |
| 5 | `policy <pidA> rr 20` | *"Deeper than nice — a real `chrt` switches the whole scheduler to real-time RR."* (needs sudo; else `policy <pid> other`) |
| 6 | `stop <pidA>` | **SIGSTOP** — freeze it. State becomes **T (stopped)**. |
| 7 | `cont <pidA>` | **SIGCONT** — it resumes. |

**Prove it live (2nd terminal):** `top` — watch the two python3 rows and their
CPU%. Or `ps -o pid,ni,%cpu,psr,comm -C python3`.

### 🏎️ The Grand Prix (crowd-pleaser — do this one!)

| # | Type this | What happens / what to say |
|---|-----------|----------------------------|
| 1 | `race` | Two real racers, ONE core, live progress bars. *"Nobody scripted a winner — the Linux scheduler decides."* |
| 2 | `Ctrl-C` | Leave the broadcast — **the racers keep running**. |
| 3 | `nice <pid> 19` | Sabotage one racer with a real `renice`. |
| 4 | `race` | Rejoin — watch the sabotaged racer fall behind and lose. `WINNER` podium at the end. |

Anytime: **`live`** = full dashboard (CPU bars, sparklines, core lanes, event
feed) updating every second until Ctrl-C. **`web`** = browser wall display on
port 8000 for the projector.

**Say:** *"Nice value, CPU share, run-state — all real, all from the kernel.
That's CPU scheduling and signals, not slides."*

---

## 🕑 PART 2 — Resources: Memory & Deadlock (combined) — ~4 min

The idea that ties them: **a process holds resources (memory + locks); killing
it frees BOTH.**

### Memory (real RAM)
| Type this | What happens / what to say |
|-----------|----------------------------|
| `spawn mem 100` | A real process allocates **and touches** 100 MB. |
| `watch` (or `ps`) | Its **RSS** climbs to ~100 MB — real resident memory. |
| `proc <pid>` | Show live `/proc/<pid>`: **VmRSS**, faults, policy, state, nice. |
| `page <pid>` | Real **minor/major page faults** from /proc — watch minor faults climb. |
| *(2nd terminal)* | `cat /proc/<pid>/status \| grep VmRSS` — same number; `vmstat 1 3`. |

### Files (real descriptors)
| Type this | What happens / what to say |
|-----------|----------------------------|
| `spawn file` | A real process opens a file + a pipe and **fsyncs** to disk. |
| `files <pid>` | Its **real open fds** from `/proc/<pid>/fd`: file (fd 3), pipe (fds 4/5). |
| *(2nd terminal)* | `lsof -p <pid>` — the exact same descriptors. |

### Deadlock (real file locks)
| Type this | What happens / what to say |
|-----------|----------------------------|
| `deadlock` | Two real processes take **flock** locks in opposite order. |
| *(wait ~3s)* | Let each grab its first lock and reach for the second. |
| `graph` | **Wait-for cycle**: P_A → P_B → P_A. *"A real deadlock — flock has no auto-detect."* |
| `proc <pid>` | Each is **blocked in the kernel**: `wchan = locks_lock_inode_wait`. |
| *(2nd terminal)* | `ps -o pid,stat,wchan -C python3` — both `S` in `locks_...`. |
| `kill <pid>` | **SIGKILL** a victim — BOOM — frees its lock **and** memory. |
| `graph` | Green **DEADLOCK RESOLVED** banner — the other process unblocked, for real. |

### Zombie (30-second encore)
| Type this | What happens / what to say |
|-----------|----------------------------|
| `spawn zombie` | A child dies unreaped → **state Z**. *"A zombie is an exit status nobody collected."* |
| `kill <zombie>` | Nothing! You can't kill what's already dead. |
| `kill <parent>` | init adopts + reaps the zombie — it vanishes. |

**Say:** *"Memory and locks are both resources. One `kill` freed both and broke
the deadlock — that's how signals, memory and concurrency connect."*

---

## 🧑‍💻 SHOW YOU KNOW LINUX (sprinkle throughout)

Use `!` to run real commands **inside** the tool, or flip to the 2nd terminal:

| Type this | Shows |
|-----------|-------|
| `! ps -o pid,stat,ni,%cpu,rss,comm -C python3` | your workers, real columns |
| `! top` (or `! top -bn1 \| head`) | live scheduler view |
| `! cat /proc/<pid>/status` | state, VmRSS, threads |
| `! cat /proc/<pid>/wchan` | what it's blocked in |
| `! kill -l` | all real signals (SIGKILL=9, SIGSTOP=19…) |
| `! nproc` / `! free -h` | cores / real memory |

`reveal on` (default) already prints the Linux command behind every action —
point at it: *"the tool isn't hiding anything; here's the real `renice` /
`kill -STOP` it ran."*

---

## 🏁 CLOSING (say this)

> "Real processes, real /proc, real signals, a real deadlock resolved with a real
> kill. I didn't click through slides — I operated a live Linux system, and you
> could have thrown any process at me. That's how an OS actually behaves."

---

## 🆘 IF SOMETHING GOES WRONG

| Problem | Fix |
|---------|-----|
| Colours look odd | `exit`, then `NO_COLOR=1 ./run.sh` |
| `taskset`/`renice` missing | `sudo apt install -y util-linux` |
| CPU% shows `—` | run `watch` (needs 2 samples) or press Enter to redraw |
| renice "permission denied" | only **negative** nice needs sudo; use 1–19 (deprioritize) |
| A worker won't die | `kill <pid>` (SIGKILL) always works; on exit the tool cleans up all workers |
| Lost track | type `ps` (or Enter) to redraw the real table |

**Everything is real — if in doubt, prove it with `! ps` or `! top`.**
