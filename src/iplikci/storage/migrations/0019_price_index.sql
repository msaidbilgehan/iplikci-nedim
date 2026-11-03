-- TÜFE as TCMB's EVDS publishes it (F12's V1+ part; inflation.py): one row a month and series, the index written as
-- exact decimal text. Fetched with the user's own EVDS key and read beside the analysis by the Değerlendirme screen;
-- the analysis does not use it, so the rebuild does not carry it: the key fetches it again.
CREATE TABLE price_index (
    series     TEXT NOT NULL,  -- EVDS's code: TP.FG.J0
    month      TEXT NOT NULL,  -- YYYY-MM
    value      TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (series, month)
);
