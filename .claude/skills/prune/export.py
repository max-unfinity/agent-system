#!/usr/bin/env python3
"""Export: gather the conversation of a whole project across sessions into one resumable record.

Prune takes one transcript and keeps the conversation. Export takes every session of a
project since a date, prunes each of them the same way, and glues the results into a
single session ready for `claude --resume`, plus an optional markdown file for a human.

Layout follows prune.py: collector (knows the platform's layout on disk) -> core (reuses
prune's pure function) -> renderers (block, markdown) -> sinks.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prune import (  # noqa: E402
    AGENT,
    DEFAULT_FRAME,
    HUMAN,
    PROJECTS,
    Turn,
    _now,
    _user_record,
    parse_chain,
    prune,
    slug,
)

HEAD = (
    "A record of the earlier conversations on this project: the human's messages and the "
    "replies of other, already closed agent sessions, in chronological order, one section "
    "per session. Tool calls, their results and reasoning have been cut out."
)

HEAD_USER_ONLY = (
    "A record of the earlier conversations on this project: the human's messages only, in "
    "chronological order, one section per session. The agents' replies, tool calls, their "
    "results and reasoning have been cut out."
)


@dataclass
class Session:
    path: str
    sid: str
    name: str
    started: str
    ended: str
    records: int
    turns: list[Turn] = field(default_factory=list)


# --- collector: the only place that knows the platform's layout on disk -------


def project_dirs(project: str, worktrees: bool = True, projects: str = PROJECTS) -> list[str]:
    """Transcript directories of a project: its own, and those of its worktrees.

    The platform names a directory after the working directory with every non-alphanumeric
    turned into a dash. Worktrees live under `<project>/.claude/worktrees/`, so theirs
    extend the project's with `--claude-worktrees-`; a bare `-` prefix would also match
    sibling and nested projects.
    """
    root = os.path.abspath(project)
    base = os.path.join(projects, slug(root))
    dirs = [base] if os.path.isdir(base) else []
    if worktrees:
        wt = os.path.join(projects, slug(os.path.join(root, ".claude", "worktrees")))
        dirs += sorted(d for d in glob.glob(wt + "-*") if os.path.isdir(d))
    return dirs


def session_name(path: str) -> tuple[str, str]:
    """(name, session-id). A human-facing name, never a uuid: the title the human gave,
    else the one the platform generated, else its slug, else the head of the id."""
    custom = ai = slug_name = sid = None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = rec.get("type")
        if t == "custom-title" and rec.get("customTitle"):
            custom = rec["customTitle"]
        elif t == "ai-title" and rec.get("aiTitle"):
            ai = rec["aiTitle"]
        if rec.get("slug"):
            slug_name = rec["slug"]
        sid = sid or rec.get("sessionId") or rec.get("session_id")
    sid = sid or os.path.basename(path)[:-6]
    return (custom or ai or slug_name or f"untitled {sid[:8]}", sid)


def started_at(path: str) -> str:
    """The first timestamp written in the file — when the session was started."""
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("timestamp"):
            return rec["timestamp"]
    return ""


def collect(
    project: str,
    since: str = "",
    worktrees: bool = True,
    projects: str = PROJECTS,
) -> list[str]:
    """Transcripts of the project's sessions *started* on or after `since`, oldest first.

    The boundary is the session's start, not its records: a session that ran past the
    boundary is taken whole or not at all, so that the thread that set its task is never
    cut off from the work that followed.
    """
    hits: list[tuple[str, str]] = []
    for d in project_dirs(project, worktrees, projects):
        for p in glob.glob(os.path.join(d, "*.jsonl")):
            ts = started_at(p)
            if ts and ts >= since:
                hits.append((ts, p))
    return [p for _, p in sorted(hits)]


# --- core ---------------------------------------------------------------------


def drop_compact_summaries(records: list[dict]) -> list[dict]:
    """Drop the retelling /compact wrote, keeping the history it was made from.

    parse_chain already steps across the compaction boundary via logicalParentUuid, so
    the pre-compaction conversation is present in full. The summary is the model's own
    paraphrase of that same conversation, stored as a user record; dropping it leaves the
    dialogue continuous, as if the compaction had never happened.
    """
    return [r for r in records if not r.get("isCompactSummary")]


def read_session(path: str, user_only: bool = False, compact_summary: bool = False) -> Session:
    records = parse_chain(path)
    if not compact_summary:
        records = drop_compact_summaries(records)
    turns = prune(records, human_only=user_only)
    name, sid = session_name(path)
    stamps = [t.timestamp for t in turns if t.timestamp]
    return Session(
        path=path,
        sid=sid,
        name=name,
        started=started_at(path),
        ended=max(stamps) if stamps else "",
        records=len(records),
        turns=turns,
    )


# --- renderers ----------------------------------------------------------------


def _when(ts: str) -> str:
    return ts[:16].replace("T", " ") if ts else "?"


def _attrs(**kw: str) -> str:
    return " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items() if v)


def _tag_attrs(**kw: str) -> str:
    """Attributes of a tag the script adds. Titles are written by hand: quotes escape."""
    return " ".join(f'{k}="{v.replace(chr(34), chr(39))}"' for k, v in kw.items() if v)


def _yaml(v: object) -> str:
    """A scalar safe in the frontmatter: json is valid yaml, and a title may hold a colon."""
    return json.dumps(v, ensure_ascii=False) if isinstance(v, str) else json.dumps(v)


def render_block(
    sessions: list[Session],
    project: str,
    since: str = "",
    frame: str = DEFAULT_FRAME,
    user_only: bool = False,
    debug: bool = False,
) -> str:
    head = _attrs(
        project=os.path.basename(os.path.abspath(project)),
        since=since,
        sessions=str(len(sessions)),
        exported_at=_now(),
    )
    parts = []
    for s in sessions:
        marks = _attrs(started=_when(s.started), ended=_when(s.ended))
        if debug:
            marks += " " + _attrs(id=s.sid, path=s.path, records=str(s.records))
        body = "\n\n".join(
            f"[{HUMAN if t.role == 'human' else AGENT}] {t.text}" for t in s.turns
        )
        parts.append(f'--- session "{s.name}" ({marks}) ---\n\n{body}')
    record = "\n\n".join(parts)
    intro = HEAD_USER_ONLY if user_only else HEAD
    return f"<pruned-context {head}>\n{intro}\n\n---\n\n{record}\n\n---\n\n{frame}\n</pruned-context>"


def render_markdown(
    sessions: list[Session],
    project: str,
    since: str = "",
    user_only: bool = False,
    debug: bool = False,
    compact_summary: bool = False,
    worktrees: bool = True,
) -> str:
    """The human's copy of the same export.

    Everything the script adds is a tag, and nothing of the conversation is touched: a
    reply is markdown itself, and any heading, rule or fence of ours would either collide
    with one of its own or force us to rewrite text that is supposed to stand verbatim.
    """
    st = stats(sessions)
    front = {
        "project": os.path.basename(os.path.abspath(project)),
        "path": os.path.abspath(project),
        "exported": _now(),
        "since": since or None,
        "boundary": "session-start",
        "user_only": user_only,
        "compact_summary": compact_summary,
        "worktrees": worktrees,
        "sessions": len(sessions),
        "turns": st["turns"],
        "chars": st["chars"],
        "words": st["words"],
        "kb": round(st["bytes"] / 1024, 1),
        "human_chars": st["human_chars"],
        "agent_chars": st["agent_chars"],
    }
    out = ["---"]
    out += [f"{k}: {_yaml(v)}" for k, v in front.items() if v is not None]
    out += ["---", ""]
    for s in sessions:
        marks = _tag_attrs(name=s.name, started=_when(s.started), ended=_when(s.ended),
                           turns=str(len(s.turns)))
        if debug:
            marks += " " + _tag_attrs(id=s.sid, records=str(s.records), path=s.path)
        out += [f"<SESSION {marks}>", ""]
        for t in s.turns:
            tag = "HUMAN-MESSAGE" if t.role == "human" else "AGENT-MESSAGE"
            out += [f"<{tag} {_tag_attrs(at=_when(t.timestamp))}>", t.text, f"</{tag}>", ""]
        out += ["</SESSION>", ""]
    return "\n".join(out)


# --- stats --------------------------------------------------------------------


def stats(sessions: list[Session]) -> dict[str, int]:
    text = "\n".join(t.text for s in sessions for t in s.turns)
    return {
        "chars": len(text),
        "words": len(text.split()),
        "bytes": len(text.encode("utf-8")),
        "turns": sum(len(s.turns) for s in sessions),
        "human_chars": sum(len(t.text) for s in sessions for t in s.turns if t.role == "human"),
        "agent_chars": sum(len(t.text) for s in sessions for t in s.turns if t.role == "agent"),
    }


# --- sinks --------------------------------------------------------------------


def sink_new_session(block: str, cwd: str, projects: str = PROJECTS) -> tuple[str, str]:
    """A new session made of a single message. Every original is left alone."""
    import uuid as _uuid

    sid = str(_uuid.uuid4())
    d = os.path.join(projects, slug(os.path.abspath(cwd)))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, sid + ".jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(_user_record(block, cwd, sid, None), ensure_ascii=False) + "\n")
    return sid, path


# --- CLI ----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("project", nargs="?", default=os.getcwd(), help="project working directory (default: cwd)")
    p.add_argument("--since", default="", help="take sessions started on or after this date, e.g. 2026-09-18")
    p.add_argument("--out", choices=["new-session", "stdout", "none"], default="new-session",
                   help="where the resumable record goes (default: new-session)")
    p.add_argument("--md", metavar="FILE", help="also write a markdown file for a human to read")
    p.add_argument("--user-only", "--human-only", dest="user_only", action="store_true",
                   help="export the human's messages only, without the agents' replies")
    p.add_argument("--compact-summary", action="store_true",
                   help="keep the summary /compact wrote (off by default: the history it was made from is kept anyway)")
    p.add_argument("--no-worktrees", dest="worktrees", action="store_false",
                   help="skip the sessions of the project's worktrees")
    p.add_argument("--debug", action="store_true", help="add session ids, paths and record counts to the output")
    p.add_argument("--frame-file", help="file holding the frame text instead of the default")
    a = p.parse_args(argv)
    a.project = os.path.abspath(a.project)

    paths = collect(a.project, a.since, a.worktrees)
    if not paths:
        sys.exit(f"export: no sessions found for {a.project}" + (f" since {a.since}" if a.since else ""))

    sessions = [read_session(p_, a.user_only, a.compact_summary) for p_ in paths]
    skipped = [s for s in sessions if not s.turns]
    sessions = [s for s in sessions if s.turns]
    if not sessions:
        sys.exit("export: no conversation turns found in any session")

    frame = open(a.frame_file, encoding="utf-8").read() if a.frame_file else DEFAULT_FRAME
    block = render_block(sessions, a.project, a.since, frame, a.user_only, a.debug)

    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(render_markdown(sessions, a.project, a.since, a.user_only, a.debug,
                                    a.compact_summary, a.worktrees))

    st = stats(sessions)
    e = sys.stderr.write
    for s in sessions:
        e(f"  {_when(s.started)}  {len(s.turns):4d} turns  {sum(len(t.text) for t in s.turns):8d} chars  {s.name}\n")
    for s in skipped:
        e(f"  {_when(s.started)}     -- no turns --                    {s.name}\n")
    e(f"export: {len(sessions)} sessions, {st['turns']} turns\n")
    e(f"export: pruned text {st['bytes'] / 1024:.1f} KB, {st['words']} words, {st['chars']} chars"
      f" (human {st['human_chars']} chars)\n")
    e(f"export: rendered block {len(block.encode('utf-8')) / 1024:.1f} KB\n")
    if a.md:
        e(f"export: markdown written to {a.md}\n")

    if a.out == "stdout":
        print(block)
    elif a.out == "new-session":
        sid, path = sink_new_session(block, a.project)
        print(sid)
        e(f"export: {path}\nexport: claude --resume {sid}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:  # output went into head/less
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        raise SystemExit(0)
