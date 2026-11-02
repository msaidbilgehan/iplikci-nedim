"""Windows: the helper that starts the service's task again after the service ended asking for it (a restart or a
restore from the interface, app.lifecycle.RESTART). Task Scheduler starts a task again only when it could not start,
never when it ended with an error code, so the ending service leaves this behind, outside the task (manager.py,
TaskScheduler.restart_after):

    pythonw -I -X utf8 -m iplikci.service.respawn <pid>

It waits for that process to end, then until the task's instance is done with, and runs the task."""

import sys

from .manager import ManagerError, TaskScheduler


def main(argv: list[str]) -> int:
    try:
        [pid] = (int(word) for word in argv)
    except ValueError:  # not one process id
        return 2
    try:
        TaskScheduler().start_after(pid)
    except ManagerError:  # schtasks refused: the service starts at the next logon, or when the app is opened
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
