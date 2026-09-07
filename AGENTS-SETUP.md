# BasketIQ — üç agentli gecə növbəsi

## Faylları yerləşdir

```
BasketIQ/
├── .claude/
│   ├── agents/
│   │   ├── builder.md          # icraçı
│   │   ├── design-critic.md    # yalnız oxuyan dizayn auditoru
│   │   └── gatekeeper.md       # qapıdan SONRA hesabat yazır
│   ├── night-prompt.md         # hər çağırışa əlavə olunan ümumi qaydalar
│   └── night-tasks.txt         # növbə
└── scripts/
    └── night.sh
```

```bash
chmod +x scripts/night.sh
git add .claude scripts && git commit -m "chore: gecə növbəsi agentləri"
```

`logs/` qovluğunu `.gitignore`-a **əlavə etmə** — səhər hesabatı commit-in
içində olsun ki, hansı işin hansı qeyd ilə gəldiyi itməsin.

## İşə sal

```bash
bash scripts/night.sh --dry-run    # növbəni yoxla
bash scripts/night.sh              # işə sal
```

## Səhər

```bash
cd ../basketiq-night-<tarix>
cat logs/report.md          # nə oldu + ⚠️ İNSAN BAXMALIDIR
cat logs/failed.txt         # nə sındı
cat logs/questions.md       # agent nədə dayandı
git log --oneline
git diff main --stat
```

Qəbul edirsənsə: `git checkout main && git merge night-<tarix>`
Etmirsənsə: `git worktree remove ../basketiq-night-<tarix> --force`

## Necə işləyir

```
tapşırıq
  → builder            kod yazır, pytest işlədir
  → design-critic      UI toxunulubsa audit edir (yazmır)
  → builder            BLOKER varsa yalnız onları düzəldir (max 2 dövrə)
  → MAŞIN QAPISI       pytest + ruff  ← COMMIT QƏRARINI BU VERİR
  → gatekeeper         commit mesajı + səhər hesabatı
  → git commit
```

Qapı sınsa: `git reset --hard`, səbəb `logs/failed.txt`-ə yazılır, növbəti
tapşırığa keçilir. **Yarımçıq iş commit olunmur.**

## Niyə gatekeeper commit qərarını vermir

Öz komandasının işini qiymətləndirən model demək olar həmişə təsdiq edir.
Ona görə `gatekeeper` yalnız `pytest` yaşıl olandan **sonra** çağırılır və
onun işi təsdiq deyil — maşının tuta bilmədiyini (silinmiş test, README
qərarına zidd dəyişiklik, udulmuş xəta, uydurma data) səhər üçün siyahıya
yazmaqdır.

## Bilinən məhdudiyyətlər

- **`ruff` qurulmayıbsa qapı SINIR.** Əvvəl bu blok susurdu — lint addımı iz
  qoymadan keçirdi və hesabat «qapı keçdi» yazırdı, halbuki kodun yarısı
  yoxlanmamışdı. İndi `gate()` `ruff-yoxdur` qaytarır, səbəb `logs/ruff.txt`-ə
  yazılır. Həlli: `pip install -r requirements.txt` (`ruff` orada elan olunub,
  konfiqurasiya `ruff.toml`-dadır).
- **Agent öz UI-ını görmür.** Playwright MCP qoşulmayıbsa dizayn işi kor gedir:
  `claude mcp add playwright npx '@playwright/mcp@latest'` — sonra
  `night-tasks.txt`-də «səhifəni aç, screenshot çək, logs/-a yaz» yaza bilərsən.
  Bu qoşulmadan **UI tapşırıqlarını gecə növbəsinə vermə**, yalnız audit tapşırığı ver.
- **`--allowedTools` Bash-ı yalnız pytest ilə məhdudlaşdırır.** Agentə `scrape.py`
  və ya `ollama` lazım olan tapşırıq versən, o tapşırıq işləməyəcək.
  Belə işləri gündüz, öz nəzarətinlə et.
- **Flaky test = itirilmiş iş.** OCR və LLM testləri təsadüfi sınırsa, düzgün
  iş də geri qaytarılacaq. Əvvəlcə `pytest -q` -ni 3 dəfə işlədib sabitliyini
  yoxla.
- **Uzun run-da kontekst dolur.** Hər tapşırıq ayrı `claude -p` çağırışıdır,
  ona görə tapşırıqlar bir-birindən müstəqil olmalıdır. «Əvvəlki addımı davam
  etdir» tipli sətir yazma.
- **Versiya fərqi.** Bayraqları `claude -p --help` ilə yoxla; `--permission-mode`
  və `--allowedTools` davranışı versiyalar arasında dəyişib.

## İlk gecə üçün məsləhət

Növbəyə **3 tapşırıq** qoy, hamısı audit tipli (kod dəyişməyən) olsun. Səhər
hesabatın keyfiyyətinə bax: agent «ölçülmədi» və «əmin deyiləm» bölmələrini
dürüst doldurubsa, sistem işləyir — sonra kod dəyişən tapşırıqlara keç.
Birinci gecədən böyük redizayn gözləmə.
