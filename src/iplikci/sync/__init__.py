"""The sync folder (ADR-0025): several computers share one set of data through a folder that a sync service mirrors
(Google Drive's, iCloud Drive's, Dropbox's), and the folder is the data's copy off the computer. Each computer keeps
its own database and writes only into its own part of the folder; what the others wrote is merged, piece by piece,
the latest change winning. This package is the folder and the merge; app.sync runs it over the data folder."""
