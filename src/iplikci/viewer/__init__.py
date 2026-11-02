"""Showing a kept document (F03): a PDF's pages as images, a spreadsheet's cells, an e-mail's text and its HTML. The
documents are untrusted input, so all of it is made in a process of its own (worker.py), with a time limit and, where
the system enforces one, a memory limit, as reading is (ADR-0005)."""
