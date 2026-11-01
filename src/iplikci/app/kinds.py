"""The kinds of background jobs (ADR-0014), named in one place: the use cases queue them, the service's worker runs
them (app.background)."""

REFRESH = "analysis.refresh"  # read what needs reading, make the analysis again, record the changes as events
PURGE = "maintenance.purge"  # forget expired sessions and old finished jobs
MAIL_FETCH = "mail.fetch"  # fetch the new messages over IMAP
INBOX_TAKE = "inbox.take"  # take in what waits in the inbox folder, without a plan (F02)
