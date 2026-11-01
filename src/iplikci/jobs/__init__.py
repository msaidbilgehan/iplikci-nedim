"""The service's background work (ADR-0014): one worker runs the queued jobs one at a time, and the scheduler
queues the periodic ones once per period, also after a sleep or a restart. What each kind of job does is handed to
the worker by the use cases in `app`."""
