# VIBO – ארכיטקטורה

מוצר וידאו קצר בסגנון טיקטוק, עם מנוע המלצות שמכוון ל-**retention** (חזרה ביום 7 וביום 30) ולא ל"דקות ביום". השם זמני.

## 1. עקרונות

1. **Implicit signals over explicit.** לייקים הם רעש. מה שנמדד: זמן צפייה יחסי, החלקה מוקדמת, צפייה חוזרת, שיתוף, שמירה, עצירה.
2. **Ranking on every request.** אין פיד מחושב מראש. כל בקשה ל-`/feed` מחשבת מחדש מתוך פרופיל שמתעדכן ברגע שאירוע מגיע.
3. **Explore/exploit קבוע.** 15% מהפיד הוא ניחוש מכוון מחוץ לפרופיל (זה מקור ה"איך הוא ידע").
4. **Session-aware.** הדירוג יודע מה קרה ב-30 השניות האחרונות, לא רק בחודש האחרון.
5. **Progress, not void.** כל סשן משאיר עקבות (אוסף, מסלול, מיומנות). זה התיקון לחולשה המרכזית של טיקטוק: תחושת הריקנות.
6. **Cold start by design.** תוכן חדש מקבל מכסת חשיפה מובטחת; משתמש חדש מקבל 8 סרטוני "בדיקה" מקטגוריות מנוגדות.

## 2. רכיבים

```
┌─────────────┐   HTTPS    ┌───────────────┐   ┌──────────────┐
│ Mobile app  │──────────▶ │  API (FastAPI)│──▶│  Ranker      │
│ RN / Expo   │◀────────── │  /feed /event │   │  (pure py)   │
└─────────────┘  video URL └──────┬────────┘   └──────┬───────┘
                                  │                   │
                          ┌───────▼───────┐   ┌───────▼───────┐
                          │ Postgres      │   │ Redis         │
                          │ users, videos │   │ user profiles │
                          │ events (raw)  │   │ session state │
                          └───────┬───────┘   │ video stats   │
                                  │           └───────────────┘
                          ┌───────▼───────┐
                          │ Worker        │  aggregates events → video_stats,
                          │ (cron / RQ)   │  cohort similarity, creator feedback
                          └───────────────┘
      S3 + CDN (video, thumbnails, HLS)     Transcoder (ffmpeg job)
```

### API (FastAPI)
- `POST /events` – batch של אירועי צפייה מהמכשיר (נשלח כל 5 שניות או בסגירת סשן).
- `GET /feed?user_id&session_id&n=8` – מחזיר 8 פריטים מדורגים. הלקוח מבקש שוב כשנשארו 3.
- `POST /videos` – העלאה: יוצר רשומה, מחזיר presigned URL ל-S3, מתזמן טרנסקוד.
- `GET /me/trail` – מה שהצטבר מהסשנים (ה"עקבות").

### Ranker (חבילת Python טהורה, בלי תלויות)
קלט: פרופיל משתמש + מצב סשן + מועמדים. פלט: רשימה מדורגת.
```
score = w_affinity * affinity(user_topics, video_topics)
      + w_quality  * video_quality_prior          # completion rate בקרב אחרים
      + w_similar  * cohort_score                 # מה אהבו משתמשים דומים
      + w_fresh    * freshness(video.age)
      - w_seen     * already_seen_penalty
      - w_fatigue  * session_fatigue(topic)       # 3 החלקות באותו נושא ⇒ נושא יורד
      + noise(exploration_temperature)
```
15% מהסלוטים מוקצים ל-explore: מועמדים עם ציון affinity נמוך אבל quality גבוה.

### Profile store (Redis)
- `user:{id}:topics` – hash של topic → משקל, דעיכה אקספוננציאלית (half-life 7 ימים).
- `session:{id}` – 20 האירועים האחרונים, TTL 30 דק'.
- `video:{id}:stats` – impressions, completions, avg_watch_ratio, shares.

### Worker
- כל 5 דקות: מאחד `events` → `video_stats`.
- כל שעה: מחשב cohort (k-means על וקטורי topic של משתמשים) → `cohort_topic_scores`.
- יומי: מדדים – D1/D7/D30 retention, regret proxy (סשנים שנגמרו בסגירה חדה אחרי >20 דק').

## 3. סכימת נתונים (Postgres)
ראה `engine/schema.sql`. טבלאות: `users`, `videos`, `video_topics`, `events`, `video_stats`, `trails`.

## 4. שלבי פיתוח

| שלב | מה | קריטריון סיום |
|---|---|---|
| 0 | Ranker טהור + סימולציה סינתטית (קיים בריפו) | `python -m engine.demo` מראה retention משופר מול baseline |
| 1 | API + Postgres + Redis, אפליקציית Expo עם פיד אנכי | 20 חברים משתמשים יומיים בלי שמבקשים |
| 2 | העלאה + טרנסקוד + CDN | יוצרים מעלים בעצמם |
| 3 | Cohort model (collaborative filtering) | לפחות 2,000 משתמשים פעילים |
| 4 | מודל ML לניבוי watch-ratio (LightGBM, לא deep) | A/B מנצח את הניקוד הידני |

## 5. מדדים שמנחים החלטות
- **North star:** D7 retention.
- **Guardrail:** regret proxy לא עולה; sessions > 45 דק' לא עולים.
- **Creator side:** זמן חציוני עד 200 צפיות ראשונות לסרטון חדש.
