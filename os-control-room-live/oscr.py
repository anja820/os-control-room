#!/usr/bin/env python3
"""
oscr.py - OS Control Room (LIVE): a cockpit over REAL Linux processes.

This is not a simulator. Every process in the table is a real OS process this
program fork/exec'd; every state, %CPU and memory figure is read live from
/proc; every stop/continue/kill sends a real signal; the deadlock is a real
file-lock deadlock between real processes; and scheduling really changes with
renice. The tool also SHOWS the exact Linux command behind each action, and
lets you run any Linux command inline with `!`, so you drive real Linux - it is
impossible to "click next" through this.

Run:  python3 oscr.py       (Linux only; needs /proc, i.e. your VM)

Two focused parts (kept short on purpose):
  1) PROCESSES & SCHEDULING - spawn real workers, watch real %CPU, renice them.
  2) RESOURCES: MEMORY & DEADLOCK - real RAM (RSS) and a real lock deadlock;
     killing a process frees BOTH its memory and its locks (the unifying idea).
"""

import os
import sys
import signal
import subprocess
import time
import shutil
from collections import deque

import ui
import procinfo as pi

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, "worker.py")
LOCKDIR = "/tmp/oscr_locks"
RACE_DEFAULT_M = 50                     # race distance in millions of iterations


class Worker:
    def __init__(self, popen, mode, display, statusfile=None, pinned=False, pid=None):
        self.popen = popen              # None for adopted pids (e.g. a zombie child)
        self.pid = pid if pid is not None else popen.pid
        self.mode = mode
        self.display = display          # short label for the table
        self.statusfile = statusfile
        self.pinned = pinned


class ControlRoom:
    def __init__(self):
        self.workers = {}               # pid -> Worker
        self.meter = pi.CpuMeter()
        self.reveal = True              # show the real Linux command per action
        self.seq = 0
        self.events = deque(maxlen=8)   # (time, message) — the kernel news feed
        self.race = None                # active Scheduler Grand Prix, if any
        self.had_cycle = False          # last graph() saw a deadlock cycle
        self.webserver = None           # optional wall-display HTTP server
        self.webport = None
        os.makedirs(LOCKDIR, exist_ok=True)

    def log(self, msg, *styles):
        """Append to the kernel-news event feed shown on the dashboard."""
        self.events.append((time.strftime("%H:%M:%S"),
                            ui.color(msg, *styles) if styles else msg))

    # ---- helpers -------------------------------------------------------

    def _hint(self, cmd):
        if self.reveal:
            print(ui.shellhint(cmd))

    def _spawn(self, mode, args, display, statusfile=None, pin=False):
        argv = []
        if pin:
            argv += ["taskset", "-c", "0"]          # pin to one core (real!)
        argv += [sys.executable, WORKER, mode] + args
        try:
            p = subprocess.Popen(argv, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        except OSError as e:
            print(ui.err(f"could not spawn: {e}"))
            return None
        w = Worker(p, mode, display, statusfile, pin)
        self.workers[p.pid] = w
        shown = " ".join(argv).replace(sys.executable, "python3").replace(WORKER, "worker.py")
        self._hint(shown + "   &")
        print(ui.ok(f"spawned REAL process PID {p.pid}  ({display})"))
        self.log(f"fork/exec → PID {p.pid} ({display}) is alive", "bright_green")
        return w

    def reap(self):
        """Reap workers that have exited so the table reflects reality."""
        for pid, w in list(self.workers.items()):
            gone = w.popen.poll() is not None if w.popen else True
            if gone and not pi.alive(pid):
                self.meter.forget(pid)
                del self.workers[pid]
                self.log(f"PID {pid} ({w.display}) exited — its memory, fds "
                         "and locks are all freed", "grey")

    def get(self, pid):
        return self.workers.get(pid)

    # ---- dashboard -----------------------------------------------------

    def render(self):
        self.reap()
        snaps = {}
        for pid in sorted(self.workers):
            s = pi.snapshot(pid, self.meter)
            if s:
                snaps[pid] = s
        ncpu = os.cpu_count() or 1
        head = (f"  {ui.color('LIVE', 'bold','bright_green')} cockpit over REAL Linux "
                f"processes   ·   managed: {len(self.workers)}   ·   host cores: {ncpu}"
                f"   ·   reveal-cmd: {'on' if self.reveal else 'off'}"
                + (f"   ·   wall display :{self.webport}" if self.webserver else ""))
        print(ui.banner("OS CONTROL ROOM  ·  live process cockpit"))
        print(head)
        print()
        print(self._process_table(snaps))
        if snaps:
            print()
            print(self._core_lanes(snaps))
        _, _, cyc = self._find_deadlock()
        if cyc:
            print()
            print(ui.alert("DEADLOCK — a real wait-for cycle is stuck in the kernel. "
                           "Type: graph", bell=False))
        if self.events:
            print()
            print(self._events_panel())
        print()
        print(ui.color("  every row is a real PID in /proc — verify any time with:  "
                       "! ps -o pid,stat,ni,%cpu,rss,comm  |  ! top", "dim"))

    def _process_table(self, snaps):
        headers = ["PID", "WORKER", "STATE", "%CPU", "TREND", "RSS(MB)", "NI",
                   "CORE", "WCHAN(kernel)"]
        aligns = ["right", "left", "left", "left", "left", "right", "right",
                  "right", "left"]
        short = {"R": "run", "S": "sleep", "D": "disk", "T": "stopped",
                 "t": "debug", "Z": "ZOMBIE", "I": "idle", "X": "dead"}
        rows = []
        for pid, snap in snaps.items():
            w = self.workers[pid]
            st = snap["state"]
            st_col = {"R": "bright_green", "S": "bright_cyan", "D": "bright_yellow",
                      "T": "bright_yellow", "Z": "bright_magenta"}.get(st, "white")
            cpu = snap["cpu"]
            cpu_cell = (ui.bar((cpu or 0.0) / 100.0, 8) +
                        (f" {cpu:3.0f}%" if cpu is not None else ui.color("   —", "dim")))
            wchan = snap["wchan"] or "-"
            rows.append([
                ui.color(str(pid), "bold"),
                w.display[:18],
                ui.color(f"{st} {short.get(st, '?')}", st_col),
                cpu_cell,
                ui.color(ui.spark(self.meter.hist(pid), 6), "bright_cyan"),
                f"{snap['rss_kb']/1024:.1f}",
                str(snap["nice"]),
                str(snap["psr"]),
                ui.color(wchan[:18], "bright_yellow") if wchan not in ("-", "0")
                else ui.color("-", "dim"),
            ])
        body = ui.table(headers, rows, aligns)
        return ui.panel("REAL PROCESS TABLE  (live from /proc — the same source ps/top read)", body)

    def _core_lanes(self, snaps):
        """One lane per CPU core: which core is each worker on RIGHT NOW?
        (field 39 of /proc/<pid>/stat). Unpinned processes hop between lanes
        as the scheduler migrates them; pinned ones ('contend', 'race') stay put."""
        ncpu = os.cpu_count() or 1
        show = sorted(set(range(min(ncpu, 8))) | {s["psr"] for s in snaps.values()})
        lanes = {c: [] for c in show}
        for pid, s in snaps.items():
            lanes[s["psr"]].append(pid)
        lines = []
        for c in show:
            cells = []
            for pid in sorted(lanes[c]):
                s = snaps[pid]
                name = self.workers[pid].display.split()[0][:12]
                cpu = s["cpu"]
                cells.append(f"{name}[{pid}] " + ui.bar((cpu or 0.0) / 100.0, 6) +
                             (f"{cpu:4.0f}%" if cpu is not None else ui.color("   —", "dim")))
            row = "   ".join(cells) if cells else ui.color("· idle (no managed worker here)", "dim")
            lines.append(ui.color(f"core {c} ", "bold") + ui.color("│ ", "grey") + row)
        return ui.panel("CPU CORES  (watch unpinned workers hop lanes; pinned ones can't)", lines)

    def _events_panel(self):
        lines = [f"{ui.color(ts, 'grey')}  {msg}" for ts, msg in self.events]
        return ui.panel("KERNEL NEWS  ·  live event feed", lines)

    def watch(self, secs=4):
        """Live monitor for a fixed number of seconds. Real data, not animation."""
        self._live_loop(time.monotonic() + secs)

    def live(self):
        """The persistent mission-control view: stays live until Ctrl-C."""
        self._live_loop(None)

    def _live_loop(self, end):
        try:
            while end is None or time.monotonic() < end:
                ui.clear()
                self.render()
                if end is None:
                    print(ui.color("\n  LIVE — re-reading /proc every second · "
                                   "Ctrl-C returns to the prompt", "dim"))
                else:
                    print(ui.color(f"\n  watching real /proc … {int(end - time.monotonic())+1}s "
                                   "left  (Ctrl-C to stop)", "dim"))
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass

    # ---- signals & scheduling -----------------------------------------

    def signal(self, pid, sig, signame, shellcmd):
        w = self.get(pid)
        if not w:
            print(ui.err(f"PID {pid} is not a managed worker")); return
        self._hint(shellcmd)
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            print(ui.warn(f"PID {pid} already gone"))
            return
        print(ui.ok(f"sent {signame} to PID {pid}"))
        if sig == signal.SIGKILL:
            print(ui.color(r"        \ | /", "bright_yellow"))
            print(ui.color("      ─ BOOM ─  ", "bold", "bright_red") +
                  ui.color(f"PID {pid} is gone — memory, fds and locks all freed at once",
                           "bright_yellow"))
            print(ui.color(r"        / | \ ", "bright_yellow"))
            self.log(f"SIGKILL → PID {pid} ({w.display}) — every resource it held is freed",
                     "bold", "bright_red")
        elif sig == signal.SIGSTOP:
            self.log(f"SIGSTOP → PID {pid} ({w.display}) frozen mid-instruction (state T)",
                     "bright_yellow")
        elif sig == signal.SIGCONT:
            self.log(f"SIGCONT → PID {pid} ({w.display}) thawed, back on the run queue",
                     "bright_green")
        else:
            self.log(f"{signame} → PID {pid} ({w.display})", "bright_cyan")

    def renice(self, pid, n):
        w = self.get(pid)
        if not w:
            print(ui.err(f"PID {pid} is not a managed worker")); return
        self._hint(f"renice {n} -p {pid}")
        try:
            os.setpriority(os.PRIO_PROCESS, pid, n)
            print(ui.ok(f"reniced PID {pid} to nice={n}  "
                        f"(higher nice = lower priority = less CPU)"))
            self.log(f"renice {n} → PID {pid} ({w.display}) — scheduler weight changed",
                     "bright_cyan")
        except (OSError, PermissionError) as e:
            print(ui.err(f"renice failed: {e}  (negative nice needs sudo)"))

    def set_policy(self, pid, policy, prio):
        """Change the REAL kernel scheduling policy with chrt (SCHED_OTHER/FIFO/RR)."""
        w = self.get(pid)
        if not w:
            print(ui.err(f"PID {pid} is not a managed worker")); return
        flag = {"other": "--other", "fifo": "--fifo", "rr": "--rr"}.get(policy)
        if not flag:
            print(ui.err("policy must be one of: other | fifo | rr")); return
        # SCHED_OTHER always uses priority 0; FIFO/RR take a real-time priority 1-99.
        p = "0" if policy == "other" else str(prio)
        cmd = f"chrt {flag} -p {p} {pid}"
        self._hint(cmd)
        try:
            out = subprocess.run(["chrt", flag, "-p", p, str(pid)],
                                 capture_output=True, text=True)
        except FileNotFoundError:
            print(ui.err("chrt not found — install util-linux:  sudo apt install -y util-linux"))
            return
        if out.returncode == 0:
            print(ui.ok(f"PID {pid} now scheduled with {policy.upper()} "
                        f"(prio {p}) — verify:  chrt -p {pid}"))
            self.log(f"chrt → PID {pid} now runs under SCHED_{policy.upper()} (prio {p})",
                     "bright_magenta")
        else:
            msg = (out.stderr or out.stdout).strip()
            print(ui.err(f"chrt failed: {msg}"))
            if policy in ("fifo", "rr"):
                cap = pi.rt_capability()
                print(ui.info(cap["reason"]))
                if cap["sudo_may_help"]:
                    print(ui.info(f"try it as root:  ! sudo chrt {flag} -p {p} {pid}"))
                else:
                    print(ui.info("this machine blocks real-time scheduling and sudo "
                                  "won't change that — see exactly why with:  caps"))
                print(ui.info(f"the idea still demos live: run  policy {pid} other  "
                              "(SCHED_OTHER always works), then shift CPU share with "
                              f"'nice {pid} <n>'."))

    def show_caps(self):
        """Show whether THIS machine allows real-time scheduling — and why not.

        Setting a real-time SCHED_FIFO/RR policy is a privileged operation, so on
        a locked-down lab machine 'policy rr/fifo' is refused (often even under
        sudo). This reads the real capability/rlimit/rt-bandwidth data from the
        kernel so the refusal becomes a teaching moment, not a broken demo — it's
        the built-in answer to `capsh --print` / `cat /proc/self/status | grep Cap`."""
        cap = pi.rt_capability()
        self._hint("grep Cap /proc/self/status ; ulimit -r ; "
                   "cat /proc/sys/kernel/sched_rt_runtime_us")

        def yn(b):
            return ui.color("yes", "bright_green") if b else ui.color("no", "bright_red")

        eff = f"{cap['cap_eff']:016x}" if cap["cap_eff"] is not None else "?"
        body = [
            f"running as         : uid {cap['euid']} " +
            ("(root)" if cap["is_root"] else "(unprivileged user)"),
            f"CAP_SYS_NICE now   : {yn(cap['has_sys_nice'])}   " +
            ui.color(f"(CapEff = {eff})", "dim"),
            f"…in bounding set   : {yn(cap['sys_nice_in_bounding'])}   " +
            ui.color("<- if 'no', not even sudo can grant it here", "dim"),
            f"RLIMIT_RTPRIO      : soft={cap['rtprio_soft']} hard={cap['rtprio_hard']}   " +
            ui.color("<- a non-root real-time-priority ceiling (0 = none)", "dim"),
            f"sched_rt_runtime_us: {cap['rt_runtime_us']}   " +
            ui.color("<- -1 = unlimited; 0 = real-time scheduling off for everyone", "dim"),
            "",
            "real-time (rr/fifo) available here : " + yn(cap["allowed"]),
            ui.color("  " + cap["reason"], "grey" if cap["allowed"] else "bright_yellow"),
        ]
        print(ui.panel("REAL-TIME SCHEDULING PERMISSIONS  "
                       "(why 'policy rr/fifo' may be refused)", body))
        if not cap["allowed"]:
            print(ui.color("  teaching point: real-time scheduling is a PRIVILEGED "
                           "operation the kernel guards. SCHED_OTHER (normal) and 'nice' "
                           "still work — demo them with:  policy <pid> other", "dim"))

    def show_page(self, pid):
        """Show REAL page-fault counters and resident memory for a process."""
        if not pi.alive(pid):
            print(ui.err(f"no process {pid}")); return
        self._hint(f"grep -E 'VmRSS|VmSize' /proc/{pid}/status ; "
                   f"awk '{{print $10, $12}}' /proc/{pid}/stat   # minflt majflt")
        snap = pi.snapshot(pid, self.meter)
        body = [
            f"VmRSS      : {snap['rss_kb']} kB   (real RAM resident right now)",
            f"minor flts : {snap['minflt']}   " +
            ui.color("<- page mapped without disk I/O (e.g. touching new heap)", "dim"),
            f"major flts : {snap['majflt']}   " +
            ui.color("<- page that required real disk I/O to bring in", "dim"),
        ]
        print(ui.panel(f"PAGING for PID {pid}  (real counters from /proc/{pid}/stat)", body))
        print(ui.color("  tip: run 'spawn mem 200' then 'page <pid>' — watch minor "
                       "faults jump as it touches every page.", "dim"))

    def show_fds(self, pid):
        """Show the REAL open file descriptors from /proc/<pid>/fd (like lsof)."""
        if not pi.alive(pid):
            print(ui.err(f"no process {pid}")); return
        self._hint(f"ls -l /proc/{pid}/fd    (or:  lsof -p {pid})")
        fds = pi.list_fds(pid)
        if not fds:
            print(ui.warn(f"no readable fds for PID {pid} "
                          "(permission? try:  ! sudo ls -l /proc/%d/fd)" % pid)); return
        rows = []
        for num, target in fds:
            kind = ("pipe" if target.startswith("pipe:") else
                    "socket" if target.startswith("socket:") else
                    "anon" if target.startswith("anon_inode:") else
                    "device" if target.startswith("/dev/") else "file")
            std = {0: "stdin", 1: "stdout", 2: "stderr"}.get(num, "")
            rows.append([ui.color(str(num), "bold"),
                         ui.color(kind, "bright_cyan"),
                         (std + "  " if std else "") + target])
        body = ui.table(["FD", "KIND", "POINTS TO"], rows, ["right", "left", "left"])
        print(ui.panel(f"OPEN FILE DESCRIPTORS for PID {pid}  (real /proc/{pid}/fd)", body))

    # ---- resources: real deadlock -------------------------------------

    def deadlock(self):
        """Spawn two REAL processes that really deadlock on file locks."""
        self.seq += 1
        a = os.path.join(LOCKDIR, f"lockA_{self.seq}")
        b = os.path.join(LOCKDIR, f"lockB_{self.seq}")
        s1 = os.path.join(LOCKDIR, f"stat1_{self.seq}")
        s2 = os.path.join(LOCKDIR, f"stat2_{self.seq}")
        for f in (s1, s2):
            try: os.remove(f)
            except OSError: pass
        print(ui.info("creating a REAL deadlock: two processes take file locks "
                      "in opposite order (flock has no kernel auto-detect)."))
        self._spawn("lock", [a, b, s1], "bank_A (holds A, wants B)", statusfile=s1)
        self._spawn("lock", [b, a, s2], "bank_B (holds B, wants A)", statusfile=s2)
        self.log("bank_A and bank_B are reaching into each other's vaults …",
                 "bright_yellow")
        print(ui.info("give them ~3s, then run:  graph   to see the wait-for cycle,"))
        print(ui.info("and:  proc <pid>   to see each one really blocked in the kernel."))

    # ---- the Scheduler Grand Prix --------------------------------------

    def race_start(self, millions):
        """Two real CPU racers pinned to ONE core — the kernel picks the winner."""
        target = millions * 1_000_000
        self.seq += 1
        print(ui.info(f"SCHEDULER GRAND PRIX — first to {millions}M iterations wins. "
                      "Both racers share ONE core; the Linux scheduler alone decides."))
        files, pids = {}, []
        for name, col in (("racer-RED", "bright_red"), ("racer-BLUE", "bright_blue")):
            sf = os.path.join(LOCKDIR, f"race_{self.seq}_{name}")
            try:
                os.remove(sf)
            except OSError:
                pass
            w = self._spawn("race", [sf, str(target)], f"{name} (core0)",
                            statusfile=sf, pin=True)
            if not w:
                return
            files[w.pid] = (name, col, sf)
            pids.append(w.pid)
        self.race = {"target": target, "pids": pids, "files": files, "done": []}
        self.log("GRAND PRIX under way — two racers, one core, zero mercy",
                 "bold", "bright_yellow")
        self.race_view()

    def race_view(self):
        """The live race broadcast. Ctrl-C leaves it; the racers keep running."""
        r = self.race
        if not r:
            print(ui.err("no race running — start one with:  race")); return
        target = r["target"]
        try:
            while True:
                ui.clear()
                print(ui.banner("SCHEDULER GRAND PRIX  ·  one core · two real processes · "
                                "the kernel picks the winner"))
                print()
                settled = True
                for pid in r["pids"]:
                    name, col, sf = r["files"][pid]
                    try:
                        with open(sf) as f:
                            txt = f.read().split()
                    except OSError:
                        txt = []
                    done = bool(txt) and txt[0] == "DONE"
                    n = int(txt[1]) if done and len(txt) > 1 else \
                        (int(txt[0]) if txt and txt[0].isdigit() else 0)
                    frac = min(1.0, n / target)
                    if done and pid not in r["done"]:
                        r["done"].append(pid)
                        self.log(f"{name} (PID {pid}) crossed the finish line!", "bold", col)
                    snap = pi.snapshot(pid, self.meter) if pi.alive(pid) else None
                    if done:
                        place = r["done"].index(pid) + 1
                        tag = ui.color(f"  ★ FINISHED #{place}", "bold", col)
                    elif snap is None:
                        tag = ui.color("  DNF — killed by the race marshal", "grey")
                    else:
                        settled = False
                        cpu = snap["cpu"]
                        tag = (f"  cpu {cpu:3.0f}%" if cpu is not None else "  cpu   —")
                        tag += f"   ni {snap['nice']:>3}   state {snap['state']}"
                        tag = ui.color(tag, "grey")
                    lane = ui.bar(frac, 46, (col,))
                    print(f"   {ui.color(name.ljust(10), 'bold', col)} P{pid:<7} "
                          f"{ui.color('┃', 'grey')}{lane}{ui.color('┃', 'grey')} "
                          f"{frac * 100:5.1f}%{tag}")
                    print()
                if settled:
                    self._race_podium()
                    break
                print(ui.color("   sabotage mid-race:  Ctrl-C → 'nice <pid> 19' or "
                               "'stop <pid>' → 'race' rejoins the broadcast", "dim"))
                print(ui.color("   the racers keep running while you're away — a real race, "
                               "not an animation", "dim"))
                time.sleep(0.5)
        except KeyboardInterrupt:
            print()
            print(ui.info("left the broadcast — racers still running. 'race' rejoins; "
                          "'nice <pid> 19' handicaps one; 'stop <pid>' freezes one."))

    def _race_podium(self):
        r, self.race = self.race, None
        print()
        if not r["done"]:
            print(ui.warn("both racers out — no winner (the marshal killed everyone?)"))
            return
        wpid = r["done"][0]
        name, col, _ = r["files"][wpid]
        for row in ui.bigtext("WINNER", "bold", col):
            print("      " + row)
        print()
        print(f"      {ui.color(name, 'bold', col)}  (PID {wpid}) — chosen by the real "
              "Linux scheduler, not by this program")
        order = [f"#{i + 1} {r['files'][p][0]} (P{p})" for i, p in enumerate(r["done"])]
        dnf = [f"DNF {r['files'][p][0]} (P{p})" for p in r["pids"] if p not in r["done"]]
        print(ui.color("      final standings:  " + "   ·   ".join(order + dnf), "grey"))
        self.log(f"GRAND PRIX result: {name} takes the win", "bold", col)

    # ---- zombies --------------------------------------------------------

    def spawn_zombie(self):
        """A real zombie: the worker forks a child that dies unreaped (state Z)."""
        self.seq += 1
        sf = os.path.join(LOCKDIR, f"zombie_{self.seq}")
        try:
            os.remove(sf)
        except OSError:
            pass
        parent = self._spawn("zombie", [sf], "zombie-parent (won't reap)", statusfile=sf)
        if not parent:
            return
        child = None
        for _ in range(20):                     # wait ≤2s for the child's pid
            try:
                with open(sf) as f:
                    child = int(f.read().strip() or "0") or None
            except (OSError, ValueError):
                child = None
            if child:
                break
            time.sleep(0.1)
        if not child:
            print(ui.warn("zombie child pid not reported yet — press Enter to redraw"))
            return
        self.workers[child] = Worker(None, "zombie-child", "ZOMBIE (unreaped)", pid=child)
        print(ui.ok(f"child PID {child} is now a REAL zombie — dead, but still in the "
                    f"process table because nobody wait()ed for it"))
        print(ui.info(f"signals can't kill what's already dead — try it! then "
                      f"kill the PARENT (PID {parent.pid}) and watch init reap the zombie"))
        self.log(f"PID {child} rose as a zombie — parent {parent.pid} refuses to reap it",
                 "bright_magenta")

    # ---- the wall display (web) ----------------------------------------

    def start_web(self, port=8000):
        """Read-only browser dashboard fed by the same /proc data (for a projector)."""
        if self.webserver:
            print(ui.info(f"wall display already live on port {self.webport}")); return
        import webdash
        try:
            self.webserver = webdash.start(self, port)
        except OSError as e:
            print(ui.err(f"could not start the wall display: {e}")); return
        self.webport = port
        ip = ""
        try:
            out = subprocess.run(["hostname", "-I"], capture_output=True,
                                 text=True, timeout=3)
            ip = (out.stdout.strip().split() or [""])[0]
        except (OSError, subprocess.SubprocessError):
            pass
        print(ui.ok(f"WALL DISPLAY live:  http://localhost:{port}" +
                    (f"   ·   http://{ip}:{port}  (other machines)" if ip else "")))
        print(ui.info("it is a read-only window onto the same /proc data — "
                      "this terminal stays mission control"))
        self.log(f"wall display broadcasting on port {port}", "bright_green")

    def _lock_status(self):
        """Read what each lock-worker actually did (held / waiting)."""
        state = {}
        for w in self.workers.values():
            if w.mode != "lock" or not w.statusfile:
                continue
            held, wait = [], None
            try:
                with open(w.statusfile) as f:
                    txt = f.read().split()
            except OSError:
                txt = []
            if "HELD" in txt:
                i = txt.index("HELD")
                if i + 1 < len(txt):
                    held = txt[i + 1].split(",")
            if "WAIT" in txt:
                i = txt.index("WAIT")
                if i + 1 < len(txt):
                    wait = txt[i + 1]
            state[w.pid] = {"held": held, "wait": wait}
        return state

    def _find_deadlock(self):
        """Wait-for edges from what the real lock workers reported.
        Returns (status, edges, cycle) with edges = [(waiter, holder, lock)]."""
        st = self._lock_status()
        holder_of = {}
        for pid, s in st.items():
            for lk in s["held"]:
                holder_of[lk] = pid
        edges = []
        for pid, s in st.items():
            if s["wait"]:
                blk = holder_of.get(s["wait"])
                if blk and blk != pid:
                    edges.append((pid, blk, s["wait"]))
        pairs = [(a, b) for a, b, _ in edges]
        cyc = any((b, a) in pairs for (a, b) in pairs)
        return st, edges, cyc

    def _name(self, pid):
        w = self.get(pid)
        return w.display.split()[0] if w else "?"

    def _cycle_diagram(self, edges):
        """Draw a 2-process deadlock as boxes locked in a circle of arrows."""
        (a, b, a_wants), (_, _, b_wants) = edges[0], edges[1]

        def box(pid, name, holds):
            l1, l2 = f"P{pid}  {name}", f"holds {holds}"
            w = max(len(l1), len(l2)) + 2
            return [f"╭{'─' * w}╮", f"│ {l1.ljust(w - 2)} │",
                    f"│ {l2.ljust(w - 2)} │", f"╰{'─' * w}╯"]

        A = box(a, self._name(a), b_wants)      # A holds what B wants
        B = box(b, self._name(b), a_wants)      # B holds what A wants
        ar = f" ── waits for {a_wants} ──▶ "
        al = f" ◀── waits for {b_wants} ── "
        m = max(len(ar), len(al))
        ar, al, gap = ar.center(m), al.center(m), " " * m
        y, r = ("bright_yellow",), ("bold", "bright_red")
        return "\n".join([
            "   " + ui.color(A[0], *y) + gap + ui.color(B[0], *y),
            "   " + ui.color(A[1], *y) + ui.color(ar, *r) + ui.color(B[1], *y),
            "   " + ui.color(A[2], *y) + ui.color(al, *r) + ui.color(B[2], *y),
            "   " + ui.color(A[3], *y) + gap + ui.color(B[3], *y),
        ])

    def graph(self):
        """Draw the wait-for graph; sound the red alert if there's a cycle."""
        self.reap()                     # drop any worker that just died
        st, edges, cyc = self._find_deadlock()
        if not st:
            print(ui.info("no lock workers running — try 'deadlock' first")); return

        if cyc and len(edges) == 2:
            print(ui.alert("DEADLOCK DETECTED — neither process can EVER proceed on its own"))
            print()
            print(self._cycle_diagram(edges))
            print()
            print(ui.color("   each is blocked inside the kernel (proc <pid> → wchan = "
                           "locks_lock_inode_wait) — flock has no auto-rescue.", "grey"))
            print(ui.color("   resolve it for real:  kill <pid>   — its lock is freed and "
                           "the other INSTANTLY unblocks", "bold", "bright_cyan"))
            self.log("DEADLOCK: " + " ⇄ ".join(f"P{p}" for p, _, _ in edges) +
                     " locked in a wait-for cycle", "bold", "bright_red")
            self.had_cycle = True
            return

        lines = []
        for a, b, lk in edges:
            lines.append(f"{ui.color('P' + str(a), 'bright_yellow')}"
                         f"{ui.color('  ── waits for ──▶  ', 'grey')}"
                         f"{ui.color('P' + str(b), 'bright_green')}"
                         f"{ui.color('  (lock ' + lk + ')', 'dim')}")
        if not lines:
            lines = [ui.color("(no process is currently waiting on a lock)", "dim")]
        if cyc:                          # a cycle bigger than 2 — still a deadlock
            lines += ["", ui.color("DEADLOCK: a cycle exists — nobody in it can proceed. "
                                   "Break it:  kill <pid>", "bold", "bright_red")]
            self.had_cycle = True
        print(ui.panel("WAIT-FOR GRAPH  (built from what the REAL processes reported)", lines))
        if not cyc and self.had_cycle:
            self.had_cycle = False
            print()
            print(ui.goodbar("DEADLOCK RESOLVED — the survivor grabbed its lock and moved on"))
            self.log("deadlock broken — the surviving process unblocked instantly",
                     "bold", "bright_green")

    # ---- /proc explorer (teaching) ------------------------------------

    def show_proc(self, pid):
        if not pi.alive(pid):
            print(ui.err(f"no process {pid}")); return
        self._hint(f"cat /proc/{pid}/status ; cat /proc/{pid}/wchan")
        snap = pi.snapshot(pid, self.meter)
        st = snap["state"]
        body = [
            f"cmdline : {pi.read_cmdline(pid)}",
            f"state   : {st}  ({pi.STATE_MEANING.get(st,'')})",
            f"VmRSS   : {snap['rss_kb']} kB  (real resident memory)",
            f"faults  : minor={snap['minflt']}  major={snap['majflt']}  (real page faults)",
            f"sched   : {snap['policy_name']}   nice={snap['nice']}   priority={snap['priority']}",
            f"threads : {snap['threads']}",
            f"wchan   : {snap['wchan'] or '-'}   " +
            ui.color("<- kernel function it is blocked in", "dim"),
        ]
        print(ui.panel(f"/proc/{pid}  (straight from the kernel)", body))

    # ---- shell passthrough --------------------------------------------

    def shell(self, cmdline):
        """Run ANY real Linux command and show its output. This is where you
        demonstrate Linux skill live (ps, top, cat /proc/…, kill, nice, …)."""
        if not cmdline.strip():
            print(ui.err("usage: ! <linux command>   e.g.  ! ps -o pid,stat,ni,comm")); return
        print(ui.color(f"   $ {cmdline}", "bold", "bright_green"))
        try:
            out = subprocess.run(cmdline, shell=True, capture_output=True,
                                 text=True, timeout=20)
            for line in (out.stdout + out.stderr).rstrip().splitlines():
                print("   " + line)
            print(ui.color(f"   (exit {out.returncode})", "dim"))
        except subprocess.TimeoutExpired:
            print(ui.err("command timed out"))

    # ---- teardown ------------------------------------------------------

    def shutdown(self):
        for pid, w in list(self.workers.items()):
            try:
                if w.popen:
                    w.popen.kill()
                else:
                    os.kill(pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        # best-effort cleanup of lock/status files
        try:
            for f in os.listdir(LOCKDIR):
                os.remove(os.path.join(LOCKDIR, f))
        except OSError:
            pass


HELP = """
COMMANDS  (everything here acts on REAL processes / real Linux)

 PART 1 — PROCESSES & SCHEDULING
   spawn cpu             fork+exec a real CPU-burning process
   contend               spawn TWO cpu workers pinned to ONE core (scheduling)
   race [millions]       SCHEDULER GRAND PRIX: two racers, one core — the
                         kernel picks the winner; sabotage with nice/stop
   live                  full mission-control dashboard, updates until Ctrl-C
   watch [secs]          same, for a fixed number of seconds (default 4)
   nice <pid> <n>        renice a process (higher n = lower priority = less CPU)
   policy <pid> <p> [pr] set REAL scheduler policy via chrt (p = other|fifo|rr)
   caps                  can this machine do real-time (rr/fifo)? show why/why not
   stop <pid>            SIGSTOP  (pause a real process)
   cont <pid>            SIGCONT  (resume it)

 PART 2 — MEMORY, FILES & DEADLOCK
   spawn mem <MB>        a real process that allocates & touches <MB> of RAM
   spawn file [path]     a real process that opens files/pipes (real fds)
   spawn zombie          fork a child that dies unreaped — a REAL zombie (Z)
   page <pid>            real page faults (minor/major) + RSS from /proc
   files <pid>           real open file descriptors from /proc/<pid>/fd (lsof)
   deadlock              two real processes deadlock on real file locks
   graph                 wait-for graph + red alert & cycle diagram if stuck
   proc <pid>            show live /proc/<pid> (state, RSS, faults, policy, wchan)
   kill <pid>            SIGKILL — frees its memory AND its locks (the big idea)
   term <pid>            SIGTERM — polite stop (the process can clean up)

 ANYTIME — REAL LINUX
   ! <command>           run ANY Linux command (ps, top, cat /proc/…, kill -l)
   web [port]            browser wall-display of the same /proc data (projector)
   reveal on|off         show/hide the real Linux command behind each action
   help                  this help          exit   quit (kills spawned workers)
"""


def boot():
    """A short mission-control boot sequence (pure theater — the checks are real)."""
    fast = not sys.stdout.isatty() or os.environ.get("OSCR_FAST")

    def pause(t):
        if not fast:
            time.sleep(t)

    ui.clear()
    print()
    print(ui.color("      CM-204  ·  OS", "dim"))
    for row in ui.bigtext("CONTROL ROOM", "bold", "bright_cyan"):
        print("      " + row)
        pause(0.05)
    print()
    checks = [
        ("mounting /proc", "ok" if os.path.isdir("/proc") else "MISSING"),
        ("cpu topology", f"{os.cpu_count() or 1} cores online"),
        ("taskset (core pinning)", "ok" if shutil.which("taskset")
         else "missing — sudo apt install util-linux"),
        ("chrt (scheduler policies)", "ok" if shutil.which("chrt") else "missing"),
        ("real-time (rr/fifo) policy", "available" if pi.rt_capability()["allowed"]
         else "restricted here — type 'caps'"),
        ("signal console", "armed"),
        ("worker binary", "worker.py ready"),
    ]
    for name, res in checks:
        pause(0.12)
        dots = "." * max(30 - len(name), 2)
        good = not any(w in res for w in ("missing", "MISSING", "restricted"))
        print(f"      {name} {ui.color(dots, 'grey')} "
              + ui.color(res, "bright_green" if good else "bright_yellow"))
    pause(0.25)
    print()
    print(ui.color("      ALL SYSTEMS GO", "bold", "bright_green")
          + ui.color("  —  every gauge in this cockpit reads the real kernel", "dim"))


def main():
    if not os.path.isdir("/proc"):
        print(ui.err("This tool needs Linux /proc. Run it on your Linux VM."))
        return
    cr = ControlRoom()
    boot()
    print(ui.color("\n  Real processes, real /proc, real signals. Type 'help', "
                   "'spawn cpu' or 'race' to begin — or press Enter for the cockpit. "
                   "'exit' quits.", "dim"))

    while True:
        try:
            line = ui.ask("\n  oscr(live)> ")
        except KeyboardInterrupt:
            print(); continue
        if not line:
            ui.clear(); cr.render(); continue

        if line.startswith("!"):
            cr.shell(line[1:]); continue

        parts = line.split()
        cmd, args = parts[0].lower(), parts[1:]

        try:
            if cmd in ("exit", "quit", "q"):
                break
            elif cmd == "help":
                print(HELP)
            elif cmd in ("ps", "status", "render", "r"):
                ui.clear(); cr.render()
            elif cmd == "spawn":
                mode = args[0] if args else ""
                if mode == "cpu":
                    cr._spawn("cpu", [], "cpu-burner")
                elif mode == "mem":
                    mb = args[1] if len(args) > 1 else "100"
                    cr._spawn("mem", [mb], f"mem-hog {mb}MB")
                elif mode == "io":
                    cr._spawn("io", [], "io-blocked")
                elif mode == "file":
                    path = args[1] if len(args) > 1 else f"/tmp/oscr_file_{cr.seq}.log"
                    cr.seq += 1
                    cr._spawn("file", [path], "file-writer")
                    print(ui.info(f"opened real fds — inspect with:  files <pid>"))
                elif mode == "zombie":
                    cr.spawn_zombie()
                else:
                    print(ui.err("usage: spawn <cpu|mem <MB>|io|file [path]|zombie>"))
            elif cmd == "contend":
                cr._spawn("cpu", [], "cpu-A (core0)", pin=True)
                cr._spawn("cpu", [], "cpu-B (core0)", pin=True)
                print(ui.info("two CPU workers now share ONE core. Run 'watch', "
                              "then 'nice <pid> 19' on one and 'watch' again."))
            elif cmd == "watch":
                cr.watch(int(args[0]) if args else 4)
                ui.clear(); cr.render()
            elif cmd == "live":
                cr.live()
                ui.clear(); cr.render()
            elif cmd == "race":
                if cr.race:
                    cr.race_view()
                else:
                    cr.race_start(int(args[0]) if args else RACE_DEFAULT_M)
            elif cmd == "web":
                cr.start_web(int(args[0]) if args else 8000)
            elif cmd in ("nice", "renice"):
                cr.renice(int(args[0]), int(args[1]))
            elif cmd == "policy":
                cr.set_policy(int(args[0]), args[1].lower(),
                              int(args[2]) if len(args) > 2 else 10)
            elif cmd == "caps":
                cr.show_caps()
            elif cmd == "stop":
                cr.signal(int(args[0]), signal.SIGSTOP, "SIGSTOP", f"kill -STOP {args[0]}")
            elif cmd == "cont":
                cr.signal(int(args[0]), signal.SIGCONT, "SIGCONT", f"kill -CONT {args[0]}")
            elif cmd == "kill":
                cr.signal(int(args[0]), signal.SIGKILL, "SIGKILL", f"kill -9 {args[0]}")
            elif cmd == "term":
                cr.signal(int(args[0]), signal.SIGTERM, "SIGTERM", f"kill {args[0]}")
            elif cmd == "deadlock":
                cr.deadlock()
            elif cmd == "graph":
                cr.graph()
            elif cmd == "proc":
                cr.show_proc(int(args[0]))
            elif cmd == "page":
                cr.show_page(int(args[0]))
            elif cmd == "files":
                cr.show_fds(int(args[0]))
            elif cmd == "reveal":
                cr.reveal = (args and args[0] == "on")
                print(ui.ok(f"reveal-cmd {'on' if cr.reveal else 'off'}"))
            elif cmd in ("sh", "shell"):
                cr.shell(" ".join(args))
            elif shutil.which(cmd):
                # They typed a real Linux command (e.g. `capsh`, `cat`, `top`)
                # without the `!` prefix the tool needs to run it.
                print(ui.err(f"'{cmd}' is a Linux command — run it with '!' in "
                             f"front:  ! {line}"))
            else:
                print(ui.err(f"unknown command '{cmd}' — type 'help'"))
        except (IndexError, ValueError):
            print(ui.err(f"bad arguments for '{cmd}' — type 'help'"))

    cr.shutdown()
    ui.clear()
    print(ui.color("\n  Control room closed. All spawned processes cleaned up.\n",
                   "bold", "bright_cyan"))


if __name__ == "__main__":
    main()
