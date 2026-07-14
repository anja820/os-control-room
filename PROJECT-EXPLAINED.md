# 📗 OS Control Room — What I Built & The Concepts Behind It

*A 2-page plain-language explainer: what the project does, what I do when I run
it, and the computer-organization / operating-system concepts it demonstrates.*

---

## 1. What this project is

**OS Control Room** is a text-based "cockpit" that manages **real Linux
processes** — not a simulation. I run it in a terminal; it launches real
programs on the machine, reads their live data straight from the kernel's
`/proc` filesystem (the same source `ps` and `top` use), and lets me control
them with real signals and real scheduling commands.

The point the professor asked for: **it cannot be a "click-next" slideshow.**
Every PID, every %CPU number, every memory figure, and the deadlock are whatever
the machine is really doing that second. PIDs change every run, so nothing can be
pre-scripted — the professor can interrupt at any moment ("now kill that one",
"show me its `/proc`") and I can, because it's all real.

**How it's built (4 small files):**
- `worker.py` — the *real* worker process. Depending on its mode it burns CPU,
  allocates and touches memory, opens files, holds file locks, or forks a zombie.
- `procinfo.py` — reads real data from `/proc/<pid>/stat` and `/status`: state,
  %CPU, memory (RSS), page faults, scheduling policy, blocked-in-kernel function.
- `oscr.py` — the control room itself: the command prompt, the live dashboard,
  and the real actions (signals, `renice`, `chrt`, deadlock detection).
- `ui.py` — colours, tables, bars (pure presentation, no OS logic).

**The clean split is the design argument:** `procinfo.py` only ever *reads* the
kernel's own files (it can't invent a number), and `worker.py` does *real* work.
That's why nothing here can be faked.

---

## 2. What I actually do when I present

I play the role of the **operating system's operator**. In order:

1. **Spawn** a real process and prove it exists (cross-check with `ps`/`top`).
2. Put **two CPU burners on one core** so they compete, then **`renice`** one and
   watch the CPU split shift live — I'm steering the scheduler.
3. Try to move a process onto a **real-time scheduling policy** with `chrt`; on
   this locked-down machine the kernel refuses it, and I use my `caps` command to
   show *why* (a privilege/isolation lesson).
4. Run the **Scheduler Grand Prix** — two processes race on one core; the kernel
   alone picks the winner; I sabotage one with `renice` and it loses.
5. Allocate **real memory** and watch **page faults** and RSS climb.
6. Open **real files/pipes** and list the process's real **file descriptors**.
7. Create a **real deadlock** with file locks, detect the wait-for cycle, then
   **kill** a process to break it — freeing its memory *and* its lock at once.
8. Spawn a **zombie** and show why you can't kill something already dead.

---

## 3. The concepts it demonstrates

| Concept | What it is | How I show it live |
|---|---|---|
| **Process vs program** | A program is a file; a process is that program *running*, with its own PID and `/proc` entry. | `spawn cpu` → a real PID appears; `! ps` confirms it. |
| **CPU & cores** | The CPU executes instructions; multiple cores run processes truly in parallel. | Core-lane view shows which core each worker is on *right now*. |
| **CPU scheduling** | With more processes than cores, the OS time-slices the CPU between them. | `contend` (two burners, one core) → each gets ~50%. |
| **Priority / `nice`** | A process's nice value re-weights how much CPU the scheduler gives it (within the normal scheduler). | `nice <pid> 19` → its share drops, the other rises, live. |
| **Scheduling policies** | The *kind* of scheduler: SCHED_OTHER (normal/CFS) vs real-time SCHED_FIFO/RR. `nice` tweaks *within* a policy; `policy` changes *which* policy. | `policy <pid> rr` uses `chrt`; `/proc` field 41 confirms the change. |
| **Privilege & isolation** | Real-time scheduling is a *privileged* operation; an unprivileged user/container can't have it. | `policy rr` is refused → `caps` reads the capability set and shows why. |
| **Process states** | R (running), S (sleeping), D (uninterruptible), T (stopped), Z (zombie). | The state column changes as I `stop`/`cont`/`kill`. |
| **Signals** | Software interrupts the OS delivers to a process: SIGSTOP, SIGCONT, SIGTERM, SIGKILL. | `stop`/`cont`/`kill` send real signals; state flips to T, then gone. |
| **Memory (RAM) & RSS** | Resident Set Size = physical RAM a process is actually using right now. | `spawn mem 200` allocates *and touches* 200 MB; RSS climbs to ~200 MB. |
| **Virtual memory & page faults** | The OS only backs a page with real RAM when it's touched; each first touch is a **minor page fault**; fetching from disk is a **major fault**. | `page <pid>` shows the real minor/major fault counters climbing. |
| **Files & descriptors** | The kernel keeps a per-process table of open file descriptors (files, pipes, sockets). | `files <pid>` lists `/proc/<pid>/fd`; `fsync` forces a durable disk write. |
| **Concurrency & deadlock** | Two processes each hold a resource and wait for the other's → a wait-for cycle nobody can escape. | `deadlock` (crossed file locks) → `graph` draws the cycle. |
| **Deadlock resolution** | Killing one process frees *all* its resources at once, unblocking the rest. | `kill <pid>` → the survivor instantly grabs its lock and proceeds. |
| **Zombies & reaping** | A finished child stays in the table until its parent `wait()`s for it; `init` reaps orphans. | `spawn zombie` → state Z; killing the parent makes it vanish. |
| **`/proc` & the kernel interface** | The kernel exposes live process data as files; standard tools just read them. | Every number in the tool comes from `/proc`; verify with `ps`, `top`, `lsof`, `chrt`, `free`, `vmstat`. |

---

## 4. The one-sentence thesis

> A process holds real resources — CPU time, memory, open files, and locks — and
> the operating system is what shares those resources out, protects them with
> privilege, and reclaims them when a process dies. This tool lets me *operate*
> that machinery live instead of describing it on a slide.
