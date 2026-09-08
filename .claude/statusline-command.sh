#!/usr/bin/env bash
# Claude Code status line script

input=$(cat)

model=$(echo "$input" | jq -r '.model.display_name // "Claude"')
effort=$(echo "$input" | jq -r '.effort.level // empty')
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
dir=$(basename "$cwd")

branch=""
[ -n "$cwd" ] && branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null)

# Context: percentage plus token counts. used_percentage is input-only, so the
# counts use total_input_tokens to match it, and it may be null early on.
# '|' delimiter, not tab: bash collapses leading IFS whitespace and shifts fields.
IFS='|' read -r pct tokens out < <(echo "$input" | jq -r '
  def h: if . >= 1000000 then "\(.*10/1000000|round/10)M"
         elif . >= 1000 then "\(.*10/1000|round/10)k"
         else "\(.)" end;
  .context_window as $c
  | ($c.total_input_tokens // 0) as $in
  | ($c.context_window_size // 0) as $size
  | (if $c.used_percentage != null then $c.used_percentage
     elif $size > 0 then $in / $size * 100
     else null end) as $p
  | [ (if $p == null then "" else ([$p, 100] | min | round | tostring) end),
      (if $size > 0 then "\($in|h)/\($size|h)" else "" end),
      (if ($c.total_output_tokens // 0) > 0 then "↑\($c.total_output_tokens|h)" else "" end) ]
  | join("|")' 2>/dev/null)

if [ -n "$pct" ]; then
  filled=$(( pct / 10 ))
  [ "$filled" -eq 0 ] && [ "$pct" -gt 0 ] && filled=1
  if   [ "$pct" -ge 90 ]; then color='\033[31m'
  elif [ "$pct" -ge 70 ]; then color='\033[33m'
  else                         color='\033[32m'
  fi
  printf -v f '%*s' "$filled" ''
  printf -v e '%*s' "$(( 10 - filled ))" ''
  ctx="$(printf "${color}%s\033[90m%s\033[0m" "${f// /█}" "${e// /░}") ${pct}%"
  detail="${tokens}${out:+ $out}"
  [ -n "$detail" ] && ctx="${ctx} $(printf '\033[2m%s\033[0m' "$detail")"
else
  ctx=$(printf '\033[90m░░░░░░░░░░\033[0m \033[2mno ctx yet\033[0m')
fi

# Line 1: [Model effort] dir | branch    Line 2: context bar
if [ -n "$effort" ]; then
  line1=$(printf '\033[36m[\033[1m%s\033[0m\033[36m \033[2m%s\033[0m\033[36m]\033[0m' "$model" "$effort")
else
  line1=$(printf '\033[36m[\033[1m%s\033[0m\033[36m]\033[0m' "$model")
fi
line1="${line1} ${dir}"
[ -n "$branch" ] && line1="${line1} $(printf '\033[2m|\033[0m') ${branch}"

printf '%s\n%s\n' "$line1" "$ctx"
