"""Notifications (ADR-0010, architecture §14): the alert rules the user keeps in rules/alerts.yaml, the texts at each
level of detail, the quiet hours and the channels that carry them. Pure but for the channels, which leave the
computer only through egress; what was sent is kept by the use cases (app.notify)."""
