#!/usr/bin/env bash
# BasketIQ — gecə növbəsi.
#   builder -> design-critic -> (düzəliş) -> MAŞIN QAPISI -> gatekeeper -> commit
#
# İstifadə:
#   bash scripts/night.sh                 # .claude/night-tasks.txt-dən oxuyur
#   bash scripts/night.sh --dry-run       # yalnız növbəni göstərir
#
# Qeyd: bu skript ƏSAS repo-da yox, ayrıca git worktree-də işləyir.
# Səhər gördüyün tək şey bir branch olur — main toxunulmamış qalır.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BRANCH="night-$(date +%m%d-%H%M)"
WORK="$REPO/../basketiq-$BRANCH"
TASKS="$REPO/.claude/night-tasks.txt"
PROMPT="$REPO/.claude/night-prompt.md"
MAX_FIX_ROUNDS=2

# --- növbəni oxu -------------------------------------------------------------
mapfile -t QUEUE < <(grep -v '^\s*#' "$TASKS" | grep -v '^\s*$')
if [ "${#QUEUE[@]}" -eq 0 ]; then echo "Növbə boşdur: $TASKS"; exit 1; fi

echo "Növbə (${#QUEUE[@]} tapşırıq):"
printf '  %s\n' "${QUEUE[@]}"
[ "${1:-}" = "--dry-run" ] && exit 0

# --- worktree ----------------------------------------------------------------
git -C "$REPO" worktree add -b "$BRANCH" "$WORK" >/dev/null || exit 1
cd "$WORK" || exit 1
mkdir -p logs

# .gitignore-dakı yerli konfiqurasiya worktree-yə düşmür, ona görə kopyalanır.
# Bunsuz TESSERACT_CMD təyin olunmur və OCR/scraper testləri (8 ədəd) sınır -
# yəni qapı heç vaxt keçmir və düzgün iş də geri qaytarılır.
if [ -f "$REPO/.env" ]; then
  cp "$REPO/.env" "$WORK/.env"
else
  echo "XƏBƏRDARLIQ: $REPO/.env yoxdur - OCR testləri sına bilər." >&2
fi
: > logs/failed.txt
echo "# Gecə hesabatı — $(date)" > logs/report.md

# venv: worktree-də yenidən qurulmur, əsas repo-nunkunu işlədirik
if [ -x "$REPO/.venv/bin/python" ]; then PY="$REPO/.venv/bin/python"
elif [ -x "$REPO/.venv/Scripts/python.exe" ]; then PY="$REPO/.venv/Scripts/python.exe"
else PY="python3"; fi

# --- maşın qapısı ------------------------------------------------------------
# Commit qərarını BU funksiya verir, agent yox.
gate() {
  "$PY" -m pytest -q > logs/pytest.txt 2>&1 || { echo "pytest"; return 1; }
  if "$PY" -m ruff --version >/dev/null 2>&1; then
    "$PY" -m ruff check . > logs/ruff.txt 2>&1 || { echo "ruff"; return 1; }
  fi
  return 0
}

run() {  # run <agent> <prompt>
  claude -p "$(cat "$PROMPT")

AGENT: $1
$2" \
    --permission-mode acceptEdits \
    --allowedTools "Read,Edit,Write,Grep,Glob,Bash($PY -m pytest*)" \
    --output-format stream-json --verbose 2>>logs/claude-errors.txt \
    | tee -a "logs/stream-$(date +%s).jsonl" >/dev/null
}

# --- əsas dövrə --------------------------------------------------------------
for TASK in "${QUEUE[@]}"; do
  echo "── $TASK"
  BASE=$(git rev-parse HEAD)

  # 1. icra
  run builder "TAPŞIRIQ: $TASK"

  # 2. UI toxunulubsa dizayn auditi + düzəliş dövrəsi
  if git diff --name-only | grep -qE 'app/(static|templates)/'; then
    for i in $(seq 1 $MAX_FIX_ROUNDS); do
      run design-critic "Dəyişikliyi audit et. Nəticəni logs/review.md-ə yaz."
      grep -q 'BLOKER' logs/review.md 2>/dev/null \
        && grep -A99 '## BLOKER' logs/review.md | grep -q '^- [^y]' || break
      run builder "Dizayn auditi BLOKER tapdı. logs/review.md-i oxu və YALNIZ
BLOKER sətirlərini düzəlt. XƏBƏRDARLIQ-lara toxunma."
    done
  fi

  # 3. qapı — burada agentin fikri soruşulmur
  if FAIL=$(gate); then
    git add -A
    run gatekeeper "Qapı keçildi. Diff-i oxu, logs/commit-msg.txt və
logs/report.md yaz."
    git commit -F logs/commit-msg.txt --no-verify -q \
      || git commit -m "night: $TASK" --no-verify -q
    echo "   ✓ commit"
  else
    echo "   ✗ $FAIL sındı — geri qaytarılır"
    { echo "## SINDI: $TASK ($FAIL)"; tail -30 "logs/$FAIL.txt"; } >> logs/failed.txt
    git reset --hard "$BASE" -q
    git clean -fd -q -e logs
  fi
done

# --- yekun -------------------------------------------------------------------
echo
echo "Branch : $BRANCH"
echo "Yol    : $WORK"
echo "Commit : $(git rev-list --count "$(git merge-base HEAD main 2>/dev/null || echo HEAD)"..HEAD 2>/dev/null || echo '?')"
echo "Sınan  : $(grep -c '^## SINDI' logs/failed.txt 2>/dev/null || echo 0)"
echo
echo "Səhər: git -C '$WORK' log --oneline && cat '$WORK/logs/report.md'"
