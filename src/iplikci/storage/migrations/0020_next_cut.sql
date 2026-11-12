-- A card statement's next cut date as it prints it ("Bir sonraki hesap kesim tarihi"; '' when it prints none). The
-- statements read before keep '' until their reader's new version reads them again.
ALTER TABLE statements ADD COLUMN next_cut TEXT NOT NULL DEFAULT '';
