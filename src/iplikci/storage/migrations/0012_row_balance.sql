-- The account's balance after a row, in minor units, where only the row prints it: a bank notice's "Güncel Bakiye".
-- NULL when the document prints none for the row.
ALTER TABLE transactions ADD COLUMN balance INTEGER;
ALTER TABLE evidence ADD COLUMN balance INTEGER;
