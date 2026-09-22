#!/usr/bin/env python3
"""Prune: drop the evidence of work from a session transcript, keep the conversation.

Layout: parser (everything that depends on the platform's format) -> core (a pure
function) -> renderer -> sink. Sinks: a new session, the same session, a hook, stdout.

The record schema is documented as internal and changes between releases, so all
parsing lives in parse_chain() and the test suite runs against a real transcript.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass

PROJECTS = os.path.expanduser("~/.claude/projects")

HEAD = (
    "A record of an earlier conversation on this thread: the human's messages and the "
    "replies of another, already closed agent session. Tool calls, their results and "
    "reasoning have been cut out."
)

# The frame goes AFTER the record, not before it. Verified: the same frame placed
# ahead of a long record does not hold — the agent answers "yes, I ran the tests"
# about work it never did. Placed after, together with the per-line role label
# "previous session agent", it holds.
DEFAULT_FRAME = """End of record. You did not have this conversation and performed none of the actions described in it: you edited no files and ran no commands. Saying "I did" about anything above is an error.

The human's intent, decisions and wording above are accurate — rely on them and do not re-litigate them. Everything the previous session agent claimed about the results of its work is an unverified claim: establish the actual state of the code only by reading files, the diff and the thread file."""

HUMAN, AGENT = "human", "previous session agent"

# Boilerplate the platform stores in user records alongside the human's own words.
NOISE = re.compile(
    r"^\s*<(local-command|command-name|command-message|system-reminder"
    r"|user-prompt-submit-hook|pruned-context)\b"
)

# A slash command record. With arguments it is how the human states a task (`/skill <request>`).
COMMAND = re.compile(r"<command-name>/?(?P<name>[^<]*)</command-name>")
COMMAND_ARGS = re.compile(r"<command-args>(?P<args>.*?)</command-args>", re.S)


def _speech(text: str) -> str | None:
    """The human's words in a user text block, or None for boilerplate."""
    cmd, args = COMMAND.search(text), COMMAND_ARGS.search(text)
    if cmd and args and args["args"].strip():
        return f"/{cmd['name'].strip()} {args['args'].strip()}"
    if not text.strip() or NOISE.match(text):
        return None
    return text


@dataclass
class Turn:
    role: str  # "human" | "agent"
    text: str
    timestamp: str


# --- parser: the only place that knows the platform's format ------------------


def parse_chain(path: str) -> list[dict]:
    """Records in the order in which they actually make up the context.

    Walk up from the tail via parentUuid. This drops branches abandoned after a
    /rewind, and at a compact_boundary record it steps across the broken link via
    logicalParentUuid — we want the whole history, including the pre-compaction part.
    """
    by_uuid: dict[str, dict] = {}
    order: list[dict] = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        order.append(rec)
        if rec.get("uuid"):
            by_uuid[rec["uuid"]] = rec

    # The tail of the file is not necessarily the tail of the chain: bookkeeping
    # records (cost-state, ai-title, mode) land last and are not part of it.
    tail = next((r for r in reversed(order) if "uuid" in r and "parentUuid" in r), None)
    if tail is None:
        return []

    chain: list[dict] = []
    seen: set[str] = set()
    cur: dict | None = tail
    while cur is not None:
        u = cur.get("uuid")
        if u in seen:  # guard against a cycle in a corrupted file
            break
        if u:
            seen.add(u)
        chain.append(cur)
        nxt = cur.get("parentUuid") or cur.get("logicalParentUuid")
        cur = by_uuid.get(nxt) if nxt else None
    chain.reverse()
    return chain


# --- core: a pure function ----------------------------------------------------


def prune(records: list[dict], human_only: bool = False) -> list[Turn]:
    turns: list[Turn] = []
    pending: list[str] = []  # text blocks of one agent turn are joined into one
    pending_ts = ""

    def flush() -> None:
        nonlocal pending, pending_ts
        if pending and not human_only:
            turns.append(Turn("agent", "\n\n".join(pending), pending_ts))
        pending = []

    for rec in records:
        if rec.get("isSidechain") or rec.get("isMeta"):
            continue
        msg = rec.get("message")
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        ts = rec.get("timestamp", "")

        if rec.get("type") == "user":
            # The platform injects prompts of its own into the user role — a subagent's
            # completion notice carries tool ids and token counts, and is evidence of
            # work, not speech. The human's own messages are never sourced "system".
            if rec.get("promptSource") == "system":
                continue
            if isinstance(content, str):
                texts = [content]
            elif isinstance(content, list):
                texts = [b["text"] for b in content if b.get("type") == "text"]
            else:
                continue
            texts = [t for t in map(_speech, texts) if t]
            if texts:
                flush()
                turns.append(Turn("human", "\n".join(texts), ts))

        elif rec.get("type") == "assistant" and isinstance(content, list):
            for block in content:
                if block.get("type") == "text" and block.get("text", "").strip():
                    pending.append(block["text"])
                    pending_ts = ts
    flush()
    return turns


# --- renderer -----------------------------------------------------------------


def render(turns: list[Turn], frame: str = DEFAULT_FRAME, **attrs: str) -> str:
    head = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items() if v)
    body = "\n\n".join(
        f"[{HUMAN if t.role == 'human' else AGENT}] {t.text}" for t in turns
    )
    return f"<pruned-context {head}>\n{HEAD}\n\n---\n\n{body}\n\n---\n\n{frame}\n</pruned-context>"


# --- sinks --------------------------------------------------------------------


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _user_record(block: str, cwd: str, session_id: str, parent: str | None) -> dict:
    return {
        "parentUuid": parent,
        "isSidechain": False,
        "type": "user",
        "uuid": str(uuid.uuid4()),
        "timestamp": _now(),
        "sessionId": session_id,
        "promptId": str(uuid.uuid4()),
        "userType": "external",
        "entrypoint": "cli",
        "cwd": cwd,
        "message": {"role": "user", "content": block},
    }


def slug(cwd: str) -> str:
    """The directory name the platform gives a working directory.

    Every character that is not a letter or a digit becomes a dash, not the slashes
    alone: a path holding an underscore or a dot otherwise misses its directory, and a
    session written beside it is one the platform never finds.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def sink_new_session(block: str, cwd: str, projects: str = PROJECTS) -> str:
    """Build a new session out of a single message. The original is left alone."""
    sid = str(uuid.uuid4())
    d = os.path.join(projects, slug(os.path.abspath(cwd)))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, sid + ".jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps(_user_record(block, cwd, sid, None), ensure_ascii=False) + "\n")
    return sid


def sink_in_place(block: str, path: str) -> None:
    """Cut the history in a live file: parentUuid=null makes the past invisible."""
    rec = json.loads(open(path, encoding="utf-8").readlines()[-1])
    sid = rec.get("sessionId") or os.path.basename(path)[:-6]
    cwd = rec.get("cwd", os.getcwd())
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(_user_record(block, cwd, sid, None), ensure_ascii=False) + "\n")


def sink_hook(block: str) -> str:
    return json.dumps(
        {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": block}},
        ensure_ascii=False,
    )


# --- CLI ----------------------------------------------------------------------


def resolve(target: str, projects: str = PROJECTS) -> str:
    if os.path.exists(target):
        return target
    hits = glob.glob(os.path.join(projects, "*", target + ".jsonl"))
    if not hits:
        sys.exit(f"prune: no such session: {target}")
    return max(hits, key=os.path.getmtime)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("target", help="session id or path to a jsonl transcript")
    p.add_argument("--out", choices=["stdout", "new-session", "in-place", "hook"], default="stdout")
    p.add_argument("--cwd", default=os.getcwd(), help="working directory of the new session")
    p.add_argument("--human-only", action="store_true", help="drop the agent's replies too")
    p.add_argument("--frame-file", help="file holding the frame text instead of the default")
    a = p.parse_args(argv)

    path = resolve(a.target)
    records = parse_chain(path)
    turns = prune(records, human_only=a.human_only)
    if not turns:
        sys.exit("prune: no conversation turns found in the transcript")

    frame = open(a.frame_file, encoding="utf-8").read() if a.frame_file else DEFAULT_FRAME
    block = render(turns, frame, session=os.path.basename(path)[:-6], pruned_at=_now())

    if a.out == "stdout":
        print(block)
    elif a.out == "hook":
        print(sink_hook(block))
    elif a.out == "in-place":
        sink_in_place(block, path)
        print(f"prune: history cut in {path}, {len(turns)} turns kept", file=sys.stderr)
    else:
        sid = sink_new_session(block, a.cwd)
        print(sid)
        print(
            f"prune: {len(records)} records -> {len(turns)} turns; claude --resume {sid}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:  # output went into head/less
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        raise SystemExit(0)
