# VIBO

פיד וידאו קצר בסגנון טיקטוק, עם מנוע המלצות שמכוון ל-retention (D7/D30) במקום לדקות ביום.
שלב 0: מנוע דירוג טהור + סימולציה. אין תלויות, Python 3.11+.

```bash
python -m engine.demo
```

תוצאה נוכחית (200 משתמשים סינתטיים, 2,000 סרטונים + 40 חדשים ביום, 30 יום):

```
ranker            D1      D7     D30   new-video reach
random          0.57    0.60    0.64              0.16
popularity      0.52    0.62    0.65              0.05
vibo       0.66    0.85    0.82              0.68
```

## מה יש כאן
| קובץ | תפקיד |
|---|---|
| `ARCHITECTURE.md` | ארכיטקטורה מלאה, שלבי פיתוח, מדדים |
| `KICKOFF_PROMPT.md` | **הפרומפט להדביק ב-Claude Code ב-VS Code** |
| `CLAUDE.md` | חוקי הפרויקט ש-Claude Code קורא אוטומטית |
| `docs/tiktok_weaknesses.md` | 10 חולשות של טיקטוק (מחקר ספטמבר 2026) והתיקון לכל אחת |
| `engine/schema.sql` | סכימת Postgres |
| `engine/models.py` | Video / Event / UserProfile / SessionState |
| `engine/ranker.py` | הרנקר: affinity, quality prior, cold start, explore 15%, topic fatigue, mood guard, series continuation |
| `engine/sim.py` | עולם סינתטי עם משתמשים בעלי טעם נסתר; המדד הוא חזרה למחרת |
| `engine/demo.py` | משווה random / popularity / vibo |

## שני לקחים שהסימולציה כבר לימדה
1. **אספקת תוכן היא חלק מהאלגוריתם.** עם 600 סרטונים בלבד, D30 של VIBO צנח כי משתמשים מיצו את הנושאים האהובים. אלגוריתם טוב בלי מספיק תוכן חדש הוא מלכודת.
2. **שלב retrieval חובה.** לדרג את כל הקטלוג בכל בקשה לא מתאים אפילו ל-2,000 סרטונים. הרנקר מקבל ~250 מועמדים; מי בוחר את ה-250 זה השלב הבא (`engine/retrieval.py`).

## שלב 1 – backend (api/)
```bash
cp .env.example .env      # פורטים ו-API_BASE (לטלפון: ה-IP של המחשב ברשת)
make dev                  # postgres + redis + api, מיגרציות, seed של 200 סרטונים ו-30 משתמשים
make test                 # pytest על SQLite + fakeredis, בלי Docker
```
פירוט ה-endpoints, המבנה וה-storage ב-`api/README.md`. Swagger: `http://localhost:8010/docs` (לפי `API_PORT` ב-.env).

## שלב 3 – worker (worker/)
`make dev` מריץ גם `worker` (RQ) ו-`cron` (RQ cron). כל 5 דקות: events → video_stats. כל שעה: k-means (k=8) → cohorts.
יומי ב-00:10 UTC: D1/D7/D30, regret_proxy, long_session_share → `metrics_daily` עם סיכום בלוג.
```bash
make jobs                   # להריץ את שלושת ה-jobs עכשיו
DAY=2026-09-27 make metrics # מדדים ליום מסוים
make worker-logs
```
הגדרות המדדים ב-`worker/metrics.py` וב-`docs/CHANGELOG.md`.

## שלב 4 – אפליקציה (app/)
Expo SDK 57 + TypeScript, iOS ואנדרואיד מאותו קוד. Expo Go לחברים, EAS Build לחנויות.
```bash
cd app && cp .env.example .env && npm install --legacy-peer-deps && npx expo start
```
פיד אנכי עם קול, prefetch של 3 הבאים, אירועים כל 5 שניות וברקע, כרטיס "סוף פרק" כל 12 סרטונים, מסך Trail,
דיווח וחסימה (דרישת החנויות לתוכן משתמשים). רשימת מוכנות לחנויות ב-`app/README.md`.

## שלב 5 – פידבק ליוצרים
`GET /videos/{id}/retention` מחשב חי מ-events (לא מחכה ל-fold): היסטוגרמת watch-ratio בדליים של 10% ועקומת retention,
עם "איפה הכי הרבה צופים עזבו". באפליקציה: Trail → My videos → סרטון, או "Stats" בתפריט ⋯ על סרטון שלך. מתרענן כל 30 שניות.

## הצעד הבא
פתח ב-VS Code, הפעל Claude Code, הדבק את `KICKOFF_PROMPT.md`.
