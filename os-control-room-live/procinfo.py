"""
procinfo.py - Read REAL process information straight from the Linux /proc
filesystem. No simulation: every number here is what the kernel reports right
now for a live process.

The Control Room uses this to show a process table that matches `ps` and `top`,
because it reads the very same source those tools read: /proc/<pid>/stat and
/proc/<pid>/status.
"""

import os
import time

CLK_TCK = os.sysconf("SC_CLK_TCK")          # clock ticks per second (usually 100)
PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")

# Human-readable meaning of the single-letter state in /proc/<pid>/stat.
STATE_MEANING = {
    "R": "running / runnable",
    "S": "sleeping (waiting for an event)",
    "D": "uninterruptible sleep (disk/lock)",
    "T": "stopped by a signal (SIGSTOP)",
    "t": "stopped by a debugger",
    "Z": "zombie (finished, not reaped)",
    "I": "idle kernel thread",
    "X": "dead",
}

# Scheduling policy numbers the kernel reports in /proc/<pid>/stat (field 41).
# These are the SAME policies `chrt` sets and Linux really schedules by.
SCHED_POLICY = {
    0: "OTHER (CFS, normal)",
    1: "FIFO (real-time)",
    2: "RR (real-time)",
    3: "BATCH",
    5: "IDLE",
    6: "DEADLINE",
}


def alive(pid):
    """True if a process with this pid currently exists."""
    return os.path.isdir(f"/proc/{pid}")


def read_stat(pid):
    """
    Parse /proc/<pid>/stat. The second field (comm) is wrapped in parentheses
    and may itself contain spaces or ')', so we split around the LAST ')'.
    Returns a dict or None if the process is gone.
    """
    try:
        with open(f"/proc/{pid}/stat") as f:
            data = f.read()
    except (OSError, ProcessLookupError):
        return None
    rparen = data.rfind(")")
    if rparen < 0:
        return None
    comm = data[data.find("(") + 1:rparen]
    rest = data[rparen + 2:].split()
    # After comm, rest[0] is field 3 (state); field N -> rest[N-3].
    try:
        return {
            "pid": pid,
            "comm": comm,
            "state": rest[0],                      # field 3
            "minflt": int(rest[7]),                # field 10  (minor page faults)
            "majflt": int(rest[9]),                # field 12  (major page faults)
            "utime": int(rest[11]),                # field 14
            "stime": int(rest[12]),                # field 15
            "priority": int(rest[15]),             # field 18
            "nice": int(rest[16]),                 # field 19
            "threads": int(rest[17]),              # field 20
            "psr": int(rest[36]),                  # field 39  (CPU it last ran on)
            "rt_priority": int(rest[37]),          # field 40  (real-time prio)
            "policy": int(rest[38]),               # field 41  (scheduling policy)
        }
    except (IndexError, ValueError):
        return None


def read_rss_kb(pid):
    """Resident memory in kB from /proc/<pid>/status (VmRSS)."""
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except (OSError, ProcessLookupError):
        pass
    return 0


def read_wchan(pid):
    """The kernel function the process is blocked in (e.g. a lock wait), or ''."""
    try:
        with open(f"/proc/{pid}/wchan") as f:
            return f.read().strip()
    except (OSError, ProcessLookupError):
        return ""


def list_fds(pid):
    """
    The REAL open file descriptors of a process, read from /proc/<pid>/fd.

    Each entry in that directory is a symlink named by the fd number (0,1,2,...)
    pointing at whatever the fd refers to: a file path, a pipe, a socket, etc.
    This is exactly the kernel's per-process file-descriptor table - the same
    thing `ls -l /proc/<pid>/fd` and `lsof -p <pid>` show. Nothing simulated.

    Returns a list of (fd_number, target_string), sorted by fd number.
    """
    fds = []
    d = f"/proc/{pid}/fd"
    try:
        names = os.listdir(d)
    except OSError:
        return fds
    for name in names:
        try:
            target = os.readlink(os.path.join(d, name))
        except OSError:
            target = "(unreadable)"
        try:
            num = int(name)
        except ValueError:
            continue
        fds.append((num, target))
    fds.sort(key=lambda t: t[0])
    return fds


def read_cmdline(pid):
    """The full argv the process was started with (NUL-separated in /proc)."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            parts = f.read().split(b"\0")
        return " ".join(p.decode(errors="replace") for p in parts if p)
    except (OSError, ProcessLookupError):
        return ""


class CpuMeter:
    """
    Compute a real %CPU for a pid by sampling total CPU ticks (utime+stime)
    between two moments in wall-clock time - the same idea `top` uses.
    """

    def __init__(self):
        self._last = {}     # pid -> (ticks, timestamp)
        self._hist = {}     # pid -> recent %CPU values (for sparklines)

    def sample(self, pid, stat):
        now = time.monotonic()
        ticks = stat["utime"] + stat["stime"]
        prev = self._last.get(pid)
        self._last[pid] = (ticks, now)
        if not prev:
            return None                      # need two samples for a rate
        dticks = ticks - prev[0]
        dt = now - prev[1]
        if dt <= 0:
            return None
        cpu = 100.0 * (dticks / CLK_TCK) / dt
        h = self._hist.setdefault(pid, [])
        h.append(cpu)
        del h[:-30]                          # keep the last 30 samples
        return cpu

    def hist(self, pid):
        """Recent real %CPU samples for a pid (oldest first)."""
        return self._hist.get(pid, [])

    def forget(self, pid):
        self._last.pop(pid, None)
        self._hist.pop(pid, None)


def snapshot(pid, meter):
    """Gather everything the dashboard needs for one process, from /proc."""
    stat = read_stat(pid)
    if not stat:
        return None
    stat["rss_kb"] = read_rss_kb(pid)
    stat["wchan"] = read_wchan(pid)
    stat["cpu"] = meter.sample(pid, stat)
    stat["policy_name"] = SCHED_POLICY.get(stat.get("policy"), f"policy#{stat.get('policy')}")
    return stat
