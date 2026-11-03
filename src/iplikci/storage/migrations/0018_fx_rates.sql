-- The exchange rates the providers published (F12, architecture §15): one row a day, currency and source, in TL for
-- one unit, written as exact decimals. A day a provider was asked for is kept in fx_days, with whether it published
-- anything (a weekend or a holiday has no TCMB bulletin), so the history is fetched once and never asked again.
-- Fetched data, not primary: the rebuild carries the rows in its dump so that it analyses with the same rates.
CREATE TABLE fx_rates (
    day        TEXT NOT NULL,   -- YYYY-MM-DD, the bulletin's own day
    currency   TEXT NOT NULL,   -- ISO code: USD, EUR, GBP, …
    source     TEXT NOT NULL,   -- RateSource: tcmb, ecb, frankfurter
    buying     TEXT NOT NULL,   -- TL for one unit; a reference rate stands for both sides
    selling    TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (day, currency, source)
);
CREATE TABLE fx_days (
    day       TEXT NOT NULL,
    source    TEXT NOT NULL,
    published INTEGER NOT NULL,  -- 1: rates came; 0: the provider published none that day
    asked_at  TEXT NOT NULL,
    PRIMARY KEY (day, source)
);
