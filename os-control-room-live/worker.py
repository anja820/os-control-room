#!/usr/bin/env python3
"""
worker.py - A REAL process that the Control Room spawns and manages.

This is NOT a simulation. When the Control Room "spawns" a worker it really
fork/execs this program, so a genuine OS process appears with its own PID,
its own entry in /proc, real CPU usage, real memory (RSS), and real reactions
to real signals (SIGSTOP/SIGCONT/SIGTERM/SIGKILL).

Modes (each demonstrates a real OS behaviour you can observe with /proc, ps,
top, etc.):

  cpu                 busy-loop -> consumes real CPU (watch %CPU, use renice)
  mem   <MB>          allocate and TOUCH memory -> real RSS grows in /proc
  io                  block reading a pipe -> real 'S'/'D' sleeping state
  file  <path>        open a real file (+a pipe), keep the fds open and append
                      durably with fsync() -> real entries in /proc/<pid>/fd.
  lock  <hold> <want> <statusfile>
                      grab file-lock <hold>, then block on <want>. Two of these
                      crossed create a REAL deadlock (flock has no auto-detect).
  race  <statusfile> <target>
                      busy-loop counting to <target>, reporting progress to
                      <statusfile>. Two of these pinned to ONE core race for
                      the CPU -> the Linux scheduler decides who wins.
  zombie <statusfile> fork a child that exits immediately and never reap it ->
                      the child becomes a REAL zombie (state Z) in /proc.

The worker writes a one-line status to <statusfile> in lock mode so the Control
Room can build the wait-for graph from what the processes actually did.
"""

import sys
import os
import time
import signal
import fcntl


def _install_clean_exit():
    # SIGTERM should end us politely (exit 0); this lets the Control Room show
    # the difference between a catchable SIGTERM and an uncatchable SIGKILL.
    def _bye(signum, frame):
        sys.exit(0)
    signal.signal(signal.SIGTERM, _bye)


def do_cpu():
    """Pure CPU burner - a real load the Linux scheduler must share out."""
    x = 0
    while True:
        # Real arithmetic in a tight loop = real %CPU in top/ps.
        x = (x * 1103515245 + 12345) & 0x7fffffff
        x = (x ^ (x >> 7)) & 0x7fffffff


def do_mem(mb):
    """Allocate AND touch memory so the pages are really resident (RSS)."""
    chunk = bytearray(mb * 1024 * 1024)
    # Touch one byte per 4 KB page so the kernel actually backs it with RAM.
    for i in range(0, len(chunk), 4096):
        chunk[i] = 1
    # Hold the memory so you can watch VmRSS in /proc/<pid>/status.
    while True:
        time.sleep(1)
        chunk[0] = (chunk[0] + 1) & 0xff   # keep it referenced


def do_io():
    """Block on a pipe read -> a real, observable sleeping process."""
    r, w = os.pipe()
    # Never write to w, so the read blocks forever in the kernel (state S).
    os.read(r, 1)


def do_file(path):
    """
    Open a REAL file and keep it open, so the process holds a genuine file
    descriptor you can inspect in /proc/<pid>/fd. We also open a pipe, so the
    fd table shows a mix of a regular file and a pipe (just like real programs).

    Each append is followed by fsync(), which forces the data to the disk - the
    real, expensive durability step a database or journal pays for. This is the
    concrete version of the 'commit' idea: after fsync returns, the bytes really
    survive a power loss; before it, they are only buffered in the page cache.
    """
    # A real regular-file fd, opened for read+write so it lingers in the fd table.
    fh = open(path, "w+")
    # A real pipe -> two more fds (read end + write end).
    r, w = os.pipe()

    n = 0
    while True:
        n += 1
        fh.write(f"record {n}: durable write at {time.time():.3f}\n")
        fh.flush()
        os.fsync(fh.fileno())      # force bytes to disk = a real 'commit'
        time.sleep(2)


def do_lock(hold, want, statusfile):
    """
    Grab lock <hold>, then try to grab <want>. Two crossed workers deadlock.

    flock() (BSD file locks) does NOT do kernel deadlock detection, so this is
    a genuine, unresolved deadlock - exactly what the Control Room detects and
    then breaks by killing a victim.
    """
    def report(line):
        try:
            with open(statusfile, "w") as f:
                f.write(line + "\n")
        except OSError:
            pass

    fh_hold = open(hold, "w")
    fcntl.flock(fh_hold, fcntl.LOCK_EX)          # really acquire the first lock
    report(f"HELD {os.path.basename(hold)}")

    # Give the other worker time to grab ITS first lock before we reach across.
    time.sleep(1.5)

    report(f"HELD {os.path.basename(hold)} WAIT {os.path.basename(want)}")
    fh_want = open(want, "w")
    fcntl.flock(fh_want, fcntl.LOCK_EX)          # BLOCKS here -> deadlock

    # Only reached if the deadlock is broken (the other process was killed).
    report(f"HELD {os.path.basename(hold)},{os.path.basename(want)}")
    while True:
        time.sleep(1)


def do_race(statusfile, target):
    """
    A CPU racer: count to <target> in a busy loop, writing progress so the
    Control Room can draw the race. Pinned to one core with a rival, the
    fraction of CPU the scheduler grants each racer directly decides the
    outcome — renice one mid-race and watch it fall behind. Nothing staged:
    the winner is genuinely chosen by the Linux scheduler.
    """
    x = 0
    n = 0
    report_every = 100_000
    while n < target:
        end = min(n + report_every, target)
        while n < end:
            # Same real arithmetic as do_cpu — every lap costs real CPU time.
            x = (x * 1103515245 + 12345) & 0x7fffffff
            n += 1
        with open(statusfile, "w") as f:
            f.write(str(n))
    with open(statusfile, "w") as f:
        f.write(f"DONE {n}")
    # Linger briefly (sleeping, not burning) so the finish shows in the table.
    time.sleep(4)


def do_zombie(statusfile):
    """
    Fork a child that exits at once — and never wait() for it. The dead child
    stays in the process table as a REAL zombie (state Z) until this parent is
    killed (init then reaps it). That is exactly what a zombie is: an exit
    status nobody has collected yet.
    """
    child = os.fork()
    if child == 0:
        os._exit(0)                          # child dies immediately
    try:
        with open(statusfile, "w") as f:
            f.write(str(child))              # tell the Control Room its pid
    except OSError:
        pass
    while True:
        time.sleep(1)                        # deliberately never os.wait()


def main(argv):
    _install_clean_exit()
    mode = argv[1] if len(argv) > 1 else "idle"

    if mode == "cpu":
        do_cpu()
    elif mode == "mem":
        mb = int(argv[2]) if len(argv) > 2 else 100
        do_mem(mb)
    elif mode == "io":
        do_io()
    elif mode == "file":
        do_file(argv[2] if len(argv) > 2 else "/tmp/oscr_file.log")
    elif mode == "lock":
        do_lock(argv[2], argv[3], argv[4])
    elif mode == "race":
        do_race(argv[2], int(argv[3]))
    elif mode == "zombie":
        do_zombie(argv[2])
    else:
        # idle: just sit in a sleeping state
        while True:
            time.sleep(1)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        sys.exit(0)
