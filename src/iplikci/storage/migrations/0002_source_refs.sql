-- Where each row is printed in its document (architecture §10, ADR-0005), as JSON: {"page": 1, "box": [x0, top,
-- x1, bottom]}, {"page": 2, "line": 14}, {"sheet": "Sayfa1", "row": 12} or {"span": [120, 168]}. Empty for a row
-- read before the readers kept it; reading the document again fills it in.
ALTER TABLE transactions ADD COLUMN ref TEXT NOT NULL DEFAULT '';
ALTER TABLE evidence ADD COLUMN ref TEXT NOT NULL DEFAULT '';
