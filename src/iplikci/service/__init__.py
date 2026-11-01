"""Running the service (ADR-0001): one process per data folder on 127.0.0.1 that serves the API, runs the job queue,
the mail connectors and the inbox watcher. Developers run it in the foreground (`iplikci servis calistir`); the
system's service manager runs the same command in the background (`iplikci servis kur`, and from Phase 6 the
installer: ADR-0017)."""
