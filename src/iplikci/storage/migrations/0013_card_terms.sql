-- What a card statement prints for paying it: this statement's due date ("Son Ödeme Tarihi", '' when it prints
-- none), the minimum payment and the card's total limit in minor units (NULL when it prints none).
ALTER TABLE statements ADD COLUMN due_date TEXT NOT NULL DEFAULT '';
ALTER TABLE statements ADD COLUMN minimum_payment INTEGER;
ALTER TABLE statements ADD COLUMN credit_limit INTEGER;
