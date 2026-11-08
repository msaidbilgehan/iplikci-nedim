"""The kinds of background jobs (ADR-0014), named in one place: the use cases queue them, the service's worker runs
them (app.background)."""

REFRESH = "analysis.refresh"  # read what needs reading, make the analysis again, record the changes as events
PURGE = "maintenance.purge"  # forget expired sessions and old finished jobs
MAIL_FETCH = "mail.fetch"  # fetch the new messages over IMAP
INBOX_TAKE = "inbox.take"  # take in what waits in the inbox folder, without a plan (F02)
BACKUP_DAILY = "backup.daily"  # the day's backup, then the expired ones go
BACKUP_NOW = "backup.take"  # a backup the user asked for
BACKUP_REHEARSAL = "backup.rehearsal"  # the month's restore rehearsal
BRIDGE_CHECK = "mail.bridge_check"  # whether the paired browser extension was seen in the last day
NOTIFY = "notify.deliver"  # the new events into notifications, and what is due sent (ADR-0010)
FX_RATES = "fx.rates"  # the day's exchange rates and the history's missing days (architecture §15)
PRICES = "prices.fetch"  # TÜFE from EVDS, with the user's key (F12's V1+ part)
TELEGRAM_DOCUMENT = "telegram.document"  # a document the paired chat sent the bot, fetched and taken in (ADR-0021)

# What each kind is, for the System screen (Turkish, as all user-facing text).
LABELS = {
    REFRESH: "Analizi yenileme",
    PURGE: "Bakım",
    MAIL_FETCH: "E-posta alımı",
    INBOX_TAKE: "Gelen klasörünü alma",
    BACKUP_DAILY: "Günlük yedek",
    BACKUP_NOW: "Elle istenen yedek",
    BACKUP_REHEARSAL: "Geri yükleme provası",
    BRIDGE_CHECK: "Tarayıcı eklentisi denetimi",
    NOTIFY: "Bildirim gönderme",
    FX_RATES: "Döviz kurlarının çekilmesi",
    PRICES: "TÜFE'nin çekilmesi (EVDS)",
    TELEGRAM_DOCUMENT: "Telegram'dan gelen belge",
}
