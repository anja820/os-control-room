# 🎤 OS Control Room — 8-Minute Presentation Script

*Presenter notes with timings. **Bold** = type at the `oscr(live)>` prompt.
"Say:" = speak roughly this. Replace `<pid>` with a real PID off the table.
Total ≈ 8:00. Have a second terminal open for cross-checks.*

> Before you start: `cd ~/os-control-room/os-control-room-live && python3 oscr.py`
> Real-time (`policy rr`) is **meant** to be refused on this container — that's a
> demo point, not a failure.

---

## ⏱ 0:00–1:00 · Opening — "this is real"

**spawn cpu**

> Say: *"This isn't a simulation. Every process you'll see is a real Linux
> process I spawn, watched live through `/proc` — the same place `ps` and `top`
> read. Here's a real one, PID `<pid>`. Let me prove it —"*

In the **2nd terminal**:
```bash
ps -o pid,stat,%cpu,comm -C python3
```

> Say: *"Same PID, really burning CPU. The PIDs change every run, so nothing here
> can be scripted. Please interrupt me and ask me to do anything to any process."*

---

## ⏱ 1:00–2:30 · CPU scheduling & priority

**contend**

> Say: *"Two CPU-hungry processes, both pinned to ONE core, so they're forced to
> compete for it."*

**watch**

> Say: *"Live %CPU from the kernel — they settle around fifty-fifty. That's the
> scheduler time-slicing one core between two processes."*

**nice `<pidB>` 19**

> Say: *"I'll lower one's priority — a real `renice`. Higher nice means 'be less
> greedy'."*

**watch**

> Say: *"Now the split has shifted — one gets the lion's share. I just steered the
> Linux scheduler live."*

**stop `<pidA>`** → **cont `<pidA>`**

> Say: *"`stop` sends a real SIGSTOP — the process freezes, state goes to T.
> `cont` sends SIGCONT and it thaws. Real signals, real state changes."*

---

## ⏱ 2:30–3:30 · Scheduling policies & privilege (the `caps` moment)

**policy `<pid>` rr 20**

> Say: *"`nice` only re-weights a process *inside* the normal scheduler. This asks
> to switch it onto a real-time policy entirely — a deeper change. Watch:"*

*(It's refused: "Operation not permitted.")*

**caps**

> Say: *"And that refusal is the lesson. Real-time scheduling is a **privileged**
> operation. This machine is an unprivileged container — `caps` reads the kernel's
> own capability data and shows CAP_SYS_NICE is missing. The OS is refusing me,
> and it would refuse root too. That's privilege separation and isolation — the
> whole reason an operating system exists."*

**policy `<pid>` other**

> Say: *"Normal scheduling still works — no privilege needed."* *(prints `[ ok ]`.)*

---

## ⏱ 3:30–4:45 · The Scheduler Grand Prix

**race**

> Say: *"Two real processes race to fifty million iterations on ONE core. Nobody
> scripted a winner — the Linux scheduler alone decides who gets the CPU when."*

Press **Ctrl-C** (leave the broadcast — racers keep running).

**nice `<pid>` 19**

> Say: *"I'll handicap one racer with a real `renice`."*

**race**

> Say: *"Rejoin — watch the sabotaged one fall behind and lose. The podium at the
> end is decided by the kernel, not by my program."*

---

## ⏱ 4:45–5:45 · Memory & page faults

**spawn mem 200**

> Say: *"A real process that allocates AND *touches* 200 megabytes of RAM."*

**page `<pid>`**

> Say: *"Asking for memory and *using* it are different. Linux only backs a page
> with real RAM when the process touches it — each first touch is a **minor page
> fault**. Watch that counter climb."*

**watch**

> Say: *"And its RSS — real resident memory — climbs to about 200 MB as it walks
> every page."*

Optional **2nd terminal**:
```bash
free -h
```

---

## ⏱ 5:45–6:15 · Files & descriptors

**spawn file** → **files `<pid>`**

> Say: *"This process opened a real file and a pipe. Here's its kernel file-
> descriptor table straight from `/proc`: standard in/out/err, a regular file, and
> a pipe. Each write is `fsync`'d — forced to disk — the real 'commit' a database
> pays for durability."*

---

## ⏱ 6:15–7:30 · Deadlock — the flagship

**deadlock**

> Say: *"Two real processes take two file locks in opposite order. Classic recipe
> for a deadlock — and `flock` has no automatic detection, so this is a genuine
> stuck state."*

*(wait ~3 seconds)*

**graph**

> Say: *"Red alert — a wait-for cycle: A holds a lock B wants, B holds a lock A
> wants. Neither can *ever* proceed on its own."*

**proc `<pid>`**

> Say: *"Each is truly blocked inside the kernel — `wchan` reads
> `locks_lock_inode_wait`. This is real, not a drawing."*

**kill `<pid>`**

> Say: *"I break it for real — SIGKILL one process. That frees its memory AND its
> lock at the same instant."*

**graph**

> Say: *"Green banner — resolved. The survivor grabbed its lock and moved on. One
> `kill` reclaimed memory and broke the deadlock — because they're all just
> resources a process holds."*

---

## ⏱ 7:30–8:00 · Zombie encore & close

**spawn zombie**

> Say: *"A child that died but whose parent never `wait()`ed for it — a real
> zombie, state Z. It's just an exit status nobody collected."*

**kill `<zombie-pid>`**

> Say: *"Nothing happens — you can't kill what's already dead."*

**kill `<parent-pid>`**

> Say: *"Kill the parent, `init` adopts and reaps it, and it vanishes."*

**Close:**

> Say: *"Real processes, real `/proc`, real signals, a real deadlock resolved with
> a real kill. I didn't click through slides — I operated a live Linux system, and
> you could have thrown any process at me. That's how an OS actually behaves."*

**exit**

---

### Timing cheatsheet
| Segment | End time |
|---|---|
| Opening | 1:00 |
| Scheduling & priority | 2:30 |
| Policies & `caps` | 3:30 |
| Grand Prix | 4:45 |
| Memory & page faults | 5:45 |
| Files | 6:15 |
| Deadlock | 7:30 |
| Zombie & close | 8:00 |

**If running long:** cut the Grand Prix (4:45) or the files segment (6:15) — the
must-keeps are Opening, Scheduling+`caps`, Deadlock, and the close.
