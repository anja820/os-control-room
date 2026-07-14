# 🎤 OS Control Room — Presentation Run Sheet

Full command list, start to finish. Type the lines at the `oscr(live)>` prompt.
Replace `<pid>` with a real PID you read off the table each time.

> On this lab machine (an unprivileged LXC container) `policy rr/fifo` is
> **supposed** to fail — that's the OS refusing a privileged operation. Explain
> it with `caps`; don't try to "fix" it live.

---

## 0. Launch (in your terminal)

```bash
cd ~/os-control-room/os-control-room-live
python3 oscr.py
```

Optional **second terminal** (for cross-checks), same folder:

```bash
cd ~/os-control-room/os-control-room-live
```

---

## 1. Opening — prove it's real

```
spawn cpu
```

Cross-check (2nd terminal) — same PID, really burning CPU:

```bash
ps -o pid,stat,%cpu,comm -C python3
```

---

## 2. Processes & CPU scheduling

```
contend
watch
nice <pidB> 19
watch
stop <pidA>
cont <pidA>
```

Cross-check (2nd terminal):

```bash
ps -o pid,ni,%cpu,psr,comm -C python3
```

---

## 3. Scheduling policies (real-time / privilege demo)

```
proc <pid>
policy <pid> rr 20
caps
policy <pid> other
proc <pid>
```

`policy rr 20` is refused → `caps` shows why (unprivileged container, no
CAP_SYS_NICE / RT budget) → `policy other` works. That's your OS-access-control
point. Optional proof it's a container:

```
! cat /proc/self/uid_map
```

**Say:** *"Real-time scheduling is a privileged kernel operation. This is an
unprivileged container, so the kernel refuses it — to me and to root alike. That
refusal is the OS enforcing isolation. Normal scheduling and priority still
work:"* → `policy other`, `nice`.

---

## 4. The Scheduler Grand Prix (crowd-pleaser)

```
race
```

Press **Ctrl-C** to leave the broadcast (racers keep running), then:

```
nice <pid> 19
race
```

---

## 5. Memory & page faults

```
spawn mem 200
page <pid>
watch
proc <pid>
```

Cross-check (2nd terminal):

```bash
cat /proc/<pid>/status | grep VmRSS
free -h
```

---

## 6. Files & descriptors

```
spawn file
files <pid>
```

Cross-check (2nd terminal):

```bash
lsof -p <pid>
```

---

## 7. Deadlock — the flagship

```
deadlock
```

Wait ~3 seconds, then:

```
graph
proc <pid>
kill <pid>
graph
```

Cross-check (2nd terminal):

```bash
cat /proc/locks
```

---

## 8. Zombie (30-second encore)

```
spawn zombie
kill <zombie-pid>
kill <parent-pid>
```

---

## 9. Optional wall display (projector)

```
web
```

Open `http://localhost:8000` in a browser.

---

## 10. Anytime — "I know Linux" moves

```
! ps -o pid,stat,ni,%cpu,rss,comm -C python3
! top -bn1 | head
! cat /proc/<pid>/status
! kill -l
! nproc
```

---

## 11. Close

```
exit
```

Auto-kills every process you spawned.

---

### Remember on stage

- Raw Linux commands need `!` in front (e.g. `! top`), or run them in the 2nd terminal.
- Real PIDs change every run — read them off the table, don't memorize.
- `policy rr/fifo` failing here is a **feature to explain with `caps`**, not a bug.
