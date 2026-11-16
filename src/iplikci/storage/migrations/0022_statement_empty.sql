-- An account list the bank printed no movement in (blank rows down to its footnote, Statement.empty): verified as it
-- stands. The statements read before keep 0 until their reader's new version reads them again.
ALTER TABLE statements ADD COLUMN empty INTEGER NOT NULL DEFAULT 0;
