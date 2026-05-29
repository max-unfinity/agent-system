#!/usr/bin/env python3
"""Telegram Bot API helper for the runner.

The runner is plain code, so it cannot use the Telegram MCP (that's exposed to
LLM agents only). It talks to the Bot API directly. Requires env vars:

    TELEGRAM_BOT_TOKEN   the bot token from @BotFather
    TELEGRAM_CHAT_ID     the chat/user id to send to

Used for: sending the final report as a document, and crash/failure alerts.
"""
from __future__ import annotations

import os
from pathlib import Path

import requests

_API = "https://api.telegram.org/bot{token}/{method}"


def _creds() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        raise RuntimeError(
            "Telegram not configured: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
        )
    return token, chat


def send_message(text: str) -> None:
    token, chat = _creds()
    r = requests.post(
        _API.format(token=token, method="sendMessage"),
        data={"chat_id": chat, "text": text},
        timeout=30,
    )
    r.raise_for_status()


def send_document(path, caption: str = "") -> None:
    token, chat = _creds()
    p = Path(path)
    with p.open("rb") as fh:
        r = requests.post(
            _API.format(token=token, method="sendDocument"),
            data={"chat_id": chat, "caption": caption},
            files={"document": (p.name, fh)},
            timeout=120,
        )
    r.raise_for_status()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Send a Telegram message or document.")
    ap.add_argument("--message")
    ap.add_argument("--document")
    ap.add_argument("--caption", default="")
    a = ap.parse_args()
    if a.message:
        send_message(a.message)
    if a.document:
        send_document(a.document, a.caption)
