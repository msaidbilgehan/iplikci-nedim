"""The program's own updates (ADR-0022): the signed manifest a release carries, where the releases are, and putting a
new version of the installed program in place on each system. No storage and no network here: the app layer fetches
through egress and keeps the state."""
