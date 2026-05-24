#!/usr/bin/env node
const { readFileSync } = require("fs");
const { basename } = require("path");

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const CHAT_ID = process.env.TELEGRAM_CHAT_ID;
const API = `https://api.telegram.org/bot${BOT_TOKEN}`;

const [,, mode, ...rest] = process.argv;

async function main() {
  if (mode === "text") {
    const text = rest.join(" ");
    const res = await fetch(`${API}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: CHAT_ID, text, parse_mode: "Markdown" }),
    });
    const json = await res.json();
    if (!json.ok) throw new Error(json.description);
    console.log("Message sent");
  } else if (mode === "file") {
    const filePath = rest[0];
    const caption = rest.slice(1).join(" ") || undefined;
    const form = new FormData();
    form.append("chat_id", CHAT_ID);
    form.append("document", new Blob([readFileSync(filePath)]), basename(filePath));
    if (caption) form.append("caption", caption);
    const res = await fetch(`${API}/sendDocument`, { method: "POST", body: form });
    const json = await res.json();
    if (!json.ok) throw new Error(json.description);
    console.log("File sent:", basename(filePath));
  } else if (mode === "photo") {
    const filePath = rest[0];
    const caption = rest.slice(1).join(" ") || undefined;
    const form = new FormData();
    form.append("chat_id", CHAT_ID);
    form.append("photo", new Blob([readFileSync(filePath)]), basename(filePath));
    if (caption) form.append("caption", caption);
    const res = await fetch(`${API}/sendPhoto`, { method: "POST", body: form });
    const json = await res.json();
    if (!json.ok) throw new Error(json.description);
    console.log("Photo sent:", basename(filePath));
  } else {
    console.error("Usage:");
    console.error("  node send.js text <message>");
    console.error("  node send.js file <path> [caption]");
    console.error("  node send.js photo <path> [caption]");
    process.exit(1);
  }
}

main().catch(e => { console.error("Error:", e.message); process.exit(1); });
