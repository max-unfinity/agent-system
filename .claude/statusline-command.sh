#!/usr/bin/env bash
# Claude Code status line script

input=$(cat)

# --- Model ---
model=$(echo "$input" | jq -r '.model.display_name // "Claude"')

# --- Directory ---
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
dir=$(basename "$cwd")

# --- Git branch ---
branch=""
if [ -n "$cwd" ]; then
  branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null)
fi

# --- Context usage ---
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
if [ -n "$used_pct" ]; then
  used_int=$(printf "%.0f" "$used_pct")
  filled=$(( used_int / 10 ))
  [ "$filled" -gt 10 ] && filled=10
  empty=$(( 10 - filled ))
  bar=$(printf '\033[32m')
  for _ in $(seq 1 "$filled"); do bar="${bar}█"; done
  bar="${bar}$(printf '\033[90m')"
  for _ in $(seq 1 "$empty");  do bar="${bar}░"; done
  bar="${bar}$(printf '\033[0m')"
  ctx="${bar} ${used_int}%"
else
  ctx="no ctx"
fi

# --- Effort ---
effort=$(echo "$input" | jq -r '.effort.level // empty')

# --- Assemble lines ---
# Line 1: [Model effort] dir (branch)
if [ -n "$effort" ]; then
  line1=$(printf '\033[36m[\033[1m%s\033[0m\033[36m \033[2m%s\033[0m\033[36m]\033[0m' "$model" "$effort")
else
  line1=$(printf '\033[36m[\033[1m%s\033[0m\033[36m]\033[0m' "$model")
fi
line1="${line1} ${dir}"
[ -n "$branch" ] && line1="${line1} $(printf '\033[2m|\033[0m') ${branch}"

# Line 2: context bar
line2="${ctx}"

printf '%s\n%s\n' "$line1" "$line2"
