# Decisions

Project decision log. One entry per non-trivial technical decision, **appended** by
worker sub-agents — never rewrite or reorder existing entries. Each entry is a single
bullet: what was decided and why (the reasoning / trade-off), in 2-4 sentences. Keep
it terse, like the entries in `docs/INDEX.md`.

- _Example_: Chose SQLite over Postgres for storage — single-file, no server to run, and the dataset is small enough that concurrency isn't a concern; revisit if write volume grows.
