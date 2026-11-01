"""Running the service (ADR-0001): one process on 127.0.0.1 that serves the API and, as Phase 3 goes on, runs the
job queue, the mail connectors and the inbox watcher. Developers run it in the foreground (`iplikci servis
calistir`); from Phase 6 the installer registers it with the system's service manager (ADR-0017)."""
