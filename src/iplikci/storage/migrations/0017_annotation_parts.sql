-- A row split into parts (F04): each part counts under its own category. A JSON list of {amount, category,
-- necessity}: amounts in the smallest unit of TL, in the row's direction, adding up to the row as it was split.
ALTER TABLE annotations ADD COLUMN parts TEXT NOT NULL DEFAULT '[]';
