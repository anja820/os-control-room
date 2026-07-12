# 📘 Understand Your OS Project — Explained From Zero

*Read this top to bottom. It assumes you know **nothing** about operating
systems. Every word is explained in plain language with everyday examples. By
the end you'll understand your whole project and be able to talk about it
confidently.*

---

## PART 0 — The absolute basics (start here)

### What is a computer program?
A **program** is just a list of instructions saved in a file — like a recipe.
The recipe by itself (sitting in a cookbook) doesn't cook anything. It's just
paper with words.

### What is a *process*?
When you actually **run** a program, the computer starts *doing* the recipe.
That "recipe being cooked right now" is called a **process**. 

> **Program = the recipe on paper. Process = the meal actually being cooked.**

You can run the same program many times, and each one is a separate process —
like three cooks making the same recipe at three stoves at once.

### What is the CPU?
The **CPU** (Central Processing Unit) is the "brain" that actually does the
work — the cook's hands. It can only do a certain amount at once. Modern CPUs
have several **cores** — think of it as having several pairs of hands (or
several cooks) so more can happen at the same time.

### What is memory (RAM)?
**RAM** (memory) is the kitchen counter — the space where the cook lays out the
ingredients they're using *right now*. It's fast but limited. When a program
runs, it uses some counter space. A program that needs lots of ingredients uses
lots of counter space.

### What is an Operating System (OS)?
The **Operating System** (like Linux, Windows, macOS) is the **head chef /
kitchen manager**. It decides:
- which cook (process) gets to use the stove (CPU) and for how long,
- who gets counter space (memory),
- what happens when two cooks both grab the same knife (a conflict),
- and it can tell a cook to pause, continue, or stop entirely.

**Linux** is one specific operating system. It's free, and it's what your
project runs on (inside a "virtual machine" — a pretend computer running inside
your real computer).

### What is a "terminal"?
A **terminal** is a text window where you type commands to the computer instead
of clicking buttons. You type a command, press Enter, the computer does it and
prints text back. That's it. Your whole project lives in a terminal.

---

## PART 1 — The idea of your project, in one breath

> **Your project is a "control room" — a text dashboard where YOU play the role
> of the operating system (the head chef). You create real programs running on
> the computer, watch them live, and boss them around: pause them, speed one up,
> slow another down, and even cause and then fix a real traffic jam between
> them.**

It's called **OS Control Room**.

The important part: **it's not pretending.** Everything on the screen is a
**real** running program on the Linux computer, with real effects. Your
professor specifically warned against "fake" demos where you just click "next"
like a slideshow. Your tool can't be faked — the numbers are whatever the real
computer is actually doing at that second.

Think of it like the control room of a power plant or an air-traffic tower:
screens showing what's really happening, and buttons that really control things.

---

## PART 2 — The key ideas, each explained like you're 10

Your demo shows off these operating-system ideas. Here's each one in simple
terms, plus how your tool shows it.

### 2.1 — Processes have a "state"
At any moment, a running program is in one of a few situations. The OS labels
each with a single letter:

| Letter | Means | Kitchen analogy |
|---|---|---|
| **R** | Running / ready to run | The cook is actively cooking |
| **S** | Sleeping (waiting for something) | The cook is waiting for water to boil |
| **D** | Waiting on the disk/a lock (can't be disturbed) | The cook is stuck waiting and won't respond |
| **T** | Stopped (frozen by a command) | You told the cook "freeze!" |
| **Z** | Zombie (finished but not cleaned up yet) | The cook left, but their apron is still hanging up |

Your control room shows this letter for every process, live.

### 2.2 — /proc: the computer's honesty window
Linux keeps a magic folder called **`/proc`** ("proc" = processes). Inside it,
there's a sub-folder for every running process, named by its number. These
folders aren't real files on a disk — they're the kernel (the core of Linux)
telling you the **truth right now** about each process: its state, how much
memory it's using, what it's waiting for, etc.

Your tool reads `/proc` to fill its dashboard. This is the same place the
famous Linux tools `ps` and `top` read from. So your numbers match theirs —
that's how you *prove* it's real.

> Analogy: `/proc` is like a live health monitor strapped to each process —
> heartbeat, temperature, everything, updated every second.

### 2.3 — PID: every process has an ID number
When a process starts, Linux gives it a unique number called a **PID**
(Process ID) — like a ticket number at a deli. You use the PID to point at a
specific process: "pause PID 4213", "kill PID 4213". PIDs are different every
time you run something, so you *can't* memorize them in advance — another reason
your demo is clearly live, not scripted.

### 2.4 — CPU scheduling: who gets the stove?
If you have more cooks (processes) than stoves (CPU cores), the OS has to take
turns — give cook A the stove for a tiny slice of time, then cook B, then A
again, super fast, thousands of times a second. This taking-of-turns is called
**scheduling**. It happens so fast it *looks* like everyone cooks at once.

**"Nice" value — politeness:** Linux lets each process have a **niceness** from
-20 to +19. A **higher** nice number means the process is being "nicer" — it
steps back and lets others use the CPU more. So **higher nice = lower priority =
less CPU**. (Confusing at first: "nicer" = gets *less*, because it's polite.)

- The command to change it is **`renice`**.
- Your tool's `nice <pid> 19` makes a process very polite (it backs off), so
  another process grabs more CPU. You literally watch the split change, e.g.
  from 50%/50% to 80%/19%.

**Pinning to one core (`taskset`):** If there are 8 cores, two cooks each get
their own stove and never compete — boring for a demo. So your tool uses the
Linux command **`taskset -c 0`** to force two CPU-hungry processes onto the
**same single stove (core 0)**. Now they must share, and changing "niceness"
visibly shifts who gets more. That's real CPU scheduling you can *see*.

### 2.5 — Signals: the OS's walkie-talkie
A **signal** is a short message the OS can send a process to tell it something
happened. Think of them as whistle blasts a referee uses. The ones your project
uses:

| Signal | Command | What it does | Analogy |
|---|---|---|---|
| **SIGSTOP** | `kill -STOP` | Freeze the process instantly | "Everybody FREEZE!" (statue game) |
| **SIGCONT** | `kill -CONT` | Un-freeze it | "Okay, move again!" |
| **SIGTERM** | `kill` | Politely ask it to finish up and leave | "Please pack up and go home" |
| **SIGKILL** | `kill -9` | Force it to stop *immediately*, no arguments | Pulling the plug |

The word **`kill`** is just the Linux command for "send a signal" — it doesn't
always mean destroy. `kill -STOP` only pauses. `kill -9` is the one that truly
ends a process.

> Fun fact for your demo: `SIGKILL` (number 9) can't be ignored or caught — the
> kernel does it *for* the process. `SIGTERM` can be caught, so a well-written
> program can save its work before leaving. Your tool shows both.

### 2.6 — Memory, for real (RSS)
When a program asks for memory, the OS gives it some counter space. But here's a
trick: asking for space and *actually using* it are different. Linux is lazy —
it only truly hands over the RAM when the program **touches** it (writes
something to it).

**RSS** (Resident Set Size) = how much real RAM a process is *actually*
using right now. Your `mem` worker asks for, say, 100 MB **and touches every
page of it**, so its RSS really grows to ~100 MB, and you can watch that number
climb in `/proc`. Real memory, not a made-up number.

### 2.7 — Locks: sharing one thing safely
Sometimes only one process can use something at a time — like a bathroom with a
lock on the door. A **lock** is exactly that: a process "locks" a resource,
uses it, then "unlocks" it. While locked, anyone else who wants it has to
**wait** outside.

Your project uses real Linux file locks called **`flock`** (file-lock). A
process locks a file; another process trying to lock the same file blocks
(waits) until the first one lets go.

### 2.8 — Deadlock: the ultimate traffic jam
Here's the classic problem. Imagine a narrow doorway and two polite people:
- Person A walks in holding the **left** door, waiting for the **right** door.
- Person B walks in holding the **right** door, waiting for the **left** door.

Neither will let go of their door until they get the other one. So they wait…
**forever**. Nobody moves. That's a **deadlock**.

In your project:
- Process A locks file **A**, then tries to lock file **B**.
- Process B locks file **B**, then tries to lock file **A**.
- Both freeze, each waiting for the lock the other is holding. A real deadlock.

**Wait-for graph:** a simple drawing of "who is waiting for whom":
`A → B` (A waits for B) and `B → A` (B waits for A). When the arrows form a
**loop** (a circle), that loop *is* the deadlock. Your `graph` command draws
this and detects the loop.

**Why it's a *real* deadlock:** the `flock` type of lock has no automatic
rescue — Linux won't fix it for you. So it's a genuine stuck situation that
**you**, the operator, must break — by killing one of the two processes. The
moment one dies, it drops its lock, and the other one immediately gets what it
was waiting for and continues. You see it resolve live.

**The big unifying idea (why memory and deadlock are in the same part):** a
process holds *resources* — both memory and locks. When you **kill** it, the OS
frees **everything** it held at once: its memory *and* its locks. So one `kill`
both reclaims memory and breaks the deadlock. That's the connection your project
highlights.

---

## PART 3 — How your project is built (the files)

Your live project lives in the folder **`os-control-room-live/`**. It's written
in **Python** (a beginner-friendly programming language). There are 4 code
files plus a launcher. Here's what each does, in plain terms.

### 3.1 — `worker.py` — the "actor" processes
This is the small program your control room runs copies of. Each copy is a real
process that does one simple job depending on the "mode" you give it:
- **`cpu`** — does pointless math forever, just to *use CPU* (for the scheduling
  demo). Like a cook chopping vegetables non-stop.
- **`mem <number>`** — grabs that many megabytes of memory and touches it all,
  so it really uses RAM.
- **`io`** — waits for something that never comes, so it sits in the "sleeping"
  state (shows the S state).
- **`lock <A> <B>`** — grabs lock A, then reaches for lock B. Two of these
  crossed = the real deadlock.

It also listens for the "please finish" signal (SIGTERM) so it can leave
politely — that's how your demo shows the difference between a polite `term` and
a forceful `kill`.

> Think of `worker.py` as a hired actor who will play any role you assign:
> "be busy," "hog memory," "wait forever," or "get into a lock standoff."

### 3.2 — `procinfo.py` — the "eyes" that read /proc
This file's only job is to **read the truth from `/proc`** for any process:
- its state letter (R/S/D/T/Z),
- its real memory use (RSS),
- its real CPU percentage (by checking how much CPU time it used over a second —
  the same math `top` does),
- what it's waiting for (called **wchan** — the exact kernel function it's stuck
  in; for the deadlock this shows `locks_lock_inode_wait`, literally "waiting
  for a file lock").

Nothing here is invented — it just reports what the kernel says.

### 3.3 — `ui.py` — the "looks" (colors and boxes)
This file only makes the screen pretty: colors, the boxes/tables you see, lining
up columns. It has **zero** operating-system logic. Keeping "how it looks"
separate from "what it does" is good, clean design — and a nice thing to mention
to your professor.

### 3.4 — `oscr.py` — the "brain" (the control room itself)
This is the main program you actually run. It:
- keeps a list of the processes you've spawned,
- draws the dashboard (using `ui.py` to display what `procinfo.py` read),
- turns your typed commands into real actions (spawn a process, send a signal,
  renice, etc.),
- detects the deadlock from what the lock-processes actually reported,
- and — importantly — **shows you the real Linux command** behind each action,
  and lets you run **any** Linux command yourself with `!`.

> `oscr` stands for **OS Control Room**. When you type `python3 oscr.py`, this
> brain wakes up and gives you the `oscr(live)>` prompt.

### 3.5 — `run.sh` — the launcher
A tiny helper so you can just type `./run.sh` instead of `python3 oscr.py`. It
checks Python exists and that you're on Linux, then starts the tool.

---

## PART 4 — Every command, explained

When you run the tool you get a prompt: `oscr(live)>`. Here's everything you can
type.

**Making & watching processes**
- **`spawn cpu`** — start a real CPU-using process.
- **`spawn mem 100`** — start a real process that uses ~100 MB of RAM.
- **`spawn io`** — start a process that just waits (shows the sleeping state).
- **`spawn file`** — start a real process that opens files + a pipe and writes
  to disk durably (with `fsync`). Use it to show real file descriptors.
- **`contend`** — start **two** CPU processes pinned to **one** core so they
  compete (this is the scheduling demo setup).
- **`watch`** — live-monitor: the screen refreshes every second for a few
  seconds so you can watch the real CPU% numbers move. (CPU% needs two peeks a
  second apart to calculate, which is why a single snapshot shows a dash.)
- **`ps`** or just pressing **Enter** — redraw the table.

**Scheduling**
- **`nice <pid> 19`** — make that process "very polite" so it gives up CPU; the
  other one then grabs more. (Runs the real `renice` underneath.)
- **`policy <pid> <other|fifo|rr> [prio]`** — change the process's *scheduling
  policy* for real (runs the real `chrt` underneath). `other` is the normal
  fair scheduler; `fifo`/`rr` are real-time policies (those need `sudo`). This
  is a deeper knob than `nice`: `nice` only re-weights within the normal
  scheduler, while `policy` switches which scheduler the kernel uses at all.

**Signals (bossing processes around)**
- **`stop <pid>`** — freeze it (SIGSTOP). Its state becomes **T**.
- **`cont <pid>`** — un-freeze it (SIGCONT).
- **`term <pid>`** — politely ask it to end (SIGTERM).
- **`kill <pid>`** — force it to end immediately (SIGKILL).

**Resources: memory & deadlock**
- **`deadlock`** — spawn the two lock processes that will really deadlock.
- **`graph`** — draw the wait-for graph and detect the deadlock loop.
- **`proc <pid>`** — show the live `/proc` details for one process (state, real
  memory, page faults, scheduling policy, what it's waiting for).
- **`page <pid>`** — show that process's real page-fault counters: **minor**
  faults (a page mapped in without touching the disk) and **major** faults (a
  page that needed real disk I/O). These come straight from `/proc/<pid>/stat`.
- **`files <pid>`** — list that process's real **open file descriptors** from
  `/proc/<pid>/fd` (the same thing `lsof -p <pid>` shows): which number points
  at which file, pipe, or socket. This is the kernel's per-process file table.

**Showing you know Linux**
- **`! <any linux command>`** — run a real Linux command right there. Examples:
  `! ps`, `! top`, `! cat /proc/4213/status`, `! kill -l`. This is where **you**
  prove you know Linux, not the tool.
- **`reveal on` / `reveal off`** — show or hide the real Linux command that the
  tool runs for each action (it's on by default, so the underlying Linux is
  always visible).

**Session**
- **`help`** — the command list. **`exit`** — quit (and it automatically cleans
  up every process it started, so nothing is left running).

---

## PART 5 — How a demo actually flows (the story you tell)

Here's the whole thing as a little story, so you understand *why* you type each
thing.

1. **"Let me prove it's real."** You type `spawn cpu`. A real process appears
   with a real PID. You flip to a second terminal and type `top` — there it is,
   same number, really using the CPU. *Nothing is faked.*

2. **"Watch the OS share the CPU."** You type `contend` — two CPU processes now
   fight over one core. `watch` shows them at about 50% each: the scheduler is
   taking turns between them.

3. **"Watch me change priorities."** You pick one process's PID and type
   `nice <pid> 19`. Now `watch` shows something like 80% / 19% — you made the OS
   favor one process over the other, with a real Linux command.

4. **"Watch me freeze and unfreeze a process."** `stop <pid>` freezes it (state
   **T**); `cont <pid>` brings it back. Real signals.

5. **"Now real memory."** `spawn mem 100` — you watch its memory (RSS) climb to
   ~100 MB in the table and in `proc <pid>`.

6. **"Now a real traffic jam."** `deadlock` starts two processes that lock in
   opposite order. `graph` shows the loop: A waits for B, B waits for A — stuck
   forever. `proc <pid>` shows each one truly frozen in the kernel's lock-wait.

7. **"And I fix it."** `kill <pid>` ends one process. That frees its lock **and**
   its memory. The other process instantly unblocks. `graph` now shows no loop —
   solved, for real.

8. **"Any questions? Point at any process and tell me what to do to it."** —
   because it's all live, you can.

---

## PART 6 — What's in the folder

The `OS-Capstone` folder is now built around the **one** project you present:

- **`os-control-room-live/`** — the tool itself: real processes, real Linux.
  (Everything above describes this one.)
- **`PRESENTATION-GUIDE.md`** — step-by-step demo script for presenting it.
- **`CHEATSHEET.md`** — a one-page version to keep on your phone during the demo.
- **`presentation.html`** — slides (open in a browser; arrow keys to advance).
- **`UNDERSTAND-THIS-PROJECT.md`** — this explainer.
- **`cm-204-capstone-vesanja.new.pdf`** — the original project proposal.

> **Good to mention:** you first built a *simulator* to design the system, then
> rebuilt it to control **real** Linux processes — that live version is the one
> that ships. Framing it that way ("prototype first, then the real thing") is a
> strength, not a weakness.

---

## PART 7 — Mini-glossary (quick lookups)

- **OS / Operating System** — the manager of the whole computer (Linux, here).
- **Kernel** — the innermost core of the OS that actually controls hardware.
- **Process** — a program that is currently running.
- **PID** — a process's unique ID number.
- **CPU / core** — the part that does the computing; cores let it do several
  things at once.
- **RAM / memory** — fast working space; **RSS** is how much a process really uses.
- **Scheduling** — the OS deciding who gets the CPU and when.
- **nice / renice** — a process's politeness; higher = gives up more CPU.
- **taskset** — pin a process to a specific CPU core.
- **Signal** — a short message to a process (STOP, CONT, TERM, KILL).
- **Lock (flock)** — a "one at a time" claim on a resource.
- **Deadlock** — two+ processes each waiting on what the other holds; stuck forever.
- **Wait-for graph** — a drawing of who waits for whom; a loop means deadlock.
- **/proc** — Linux's live "truth folder" about every process.
- **wchan** — the exact thing a sleeping process is waiting on.
- **Zombie** — a finished process not yet cleaned up.
- **Terminal** — the text window where you type commands.

---

### One sentence to remember
> *"I built a control room where I play the operating system and manage **real**
> Linux processes — starting them, watching them live through /proc, sharing the
> CPU with real scheduling, and causing then fixing a **real** deadlock — so
> nothing is faked or pre-recorded."*

That's your whole project. You've got this. 💪
