"""HTTP-level tests for api/. Each test states the contract it protects."""
from __future__ import annotations

import time

from engine.ranker import EXPLORE_SHARE
from tests.conftest import create_video, new_session_id, post_events, watch


def seed_catalog(client, per_topic: int = 12, topics=("cooking", "art", "music")) -> dict[str, list[dict]]:
    return {t: [create_video(client, t) for _ in range(per_topic)] for t in topics}


def feed(client, user_id: str, session_id: str, n: int = 8) -> dict:
    r = client.get("/feed", params={"user_id": user_id, "session_id": session_id, "n": n})
    assert r.status_code == 200, r.text
    return r.json()


# ----------------------------------------------------------------------------- health / users

def test_health_reports_db_and_redis(client):
    body = client.get("/health").json()
    assert body == {"ok": True, "db": True, "redis": True}


def test_device_id_resolves_to_a_stable_user_id(client):
    a = client.post("/users", json={"device_id": "phone-abc"}).json()
    b = client.post("/users", json={"device_id": "phone-abc"}).json()
    c = client.post("/users", json={"device_id": "phone-xyz"}).json()
    assert a["user_id"] == b["user_id"] != c["user_id"]


# ----------------------------------------------------------------------------- videos / upload

def test_upload_flow_returns_presigned_url_and_serves_the_file(client, db):
    created = create_video(client, "cooking", upload=False)
    assert created["upload_url"].startswith("http://testserver/uploads/")
    assert created["url"] is None, "not playable until the upload completes"

    r = client.put(created["upload_url"], content=b"hello", headers={"content-type": "video/mp4"})
    assert r.status_code == 200
    assert r.json()["url"].startswith("http://testserver/media/")
    assert client.get(r.json()["url"]).content == b"hello"


def test_upload_with_bad_token_is_rejected(client):
    created = create_video(client, "cooking", upload=False)
    url = created["upload_url"].split("?")[0] + "?token=nope&expires=9999999999"
    assert client.put(url, content=b"x").status_code == 403


def test_unfinished_uploads_never_enter_the_feed(client):
    create_video(client, "cooking", upload=False)
    create_video(client, "cooking", upload=True)
    body = feed(client, "u1", new_session_id(), n=8)
    assert len(body["items"]) == 1


# ----------------------------------------------------------------------------- feed

def test_feed_returns_n_ranked_items_with_breakdown(client):
    seed_catalog(client)
    body = feed(client, "u1", new_session_id(), n=8)
    assert len(body["items"]) == 8
    for item in body["items"]:
        assert item["url"].startswith("http://testserver/media/")
        assert "creator_id" in item
        assert set(item["breakdown"]) >= {"affinity", "quality", "fatigue", "cold_start"}
        assert item["slot"] in {"exploit", "explore", "series", "probe"}


def test_feed_never_repeats_within_a_session(client):
    seed_catalog(client)
    sid = new_session_id()
    a = {i["video_id"] for i in feed(client, "u1", sid)["items"]}
    b = {i["video_id"] for i in feed(client, "u1", sid)["items"]}
    assert len(a) == len(b) == 8 and not (a & b)


def test_feed_reflects_taste_learned_from_events(client):
    cat = seed_catalog(client, per_topic=15)
    sid = new_session_id()
    post_events(client, "u1", sid, [watch(v, 1.0, position=i) for i, v in enumerate(cat["cooking"][:5])])
    items = feed(client, "u1", new_session_id(), n=8)["items"]
    exploit = [i for i in items if i["slot"] == "exploit"]
    assert exploit and all("cooking" in i["topics"] for i in exploit)
    assert sum(1 for i in items if i["slot"] == "explore") == max(1, round(8 * EXPLORE_SHARE))


def test_feed_applies_session_fatigue_after_three_early_swipes(client):
    cat = seed_catalog(client, per_topic=15)
    sid = new_session_id()
    post_events(client, "u1", sid, [watch(v, 1.0, position=i) for i, v in enumerate(cat["cooking"][:3])])
    post_events(client, "u1", sid, [watch(v, 0.1, kind="swipe", position=3 + i) for i, v in enumerate(cat["cooking"][3:6])])
    # two pages of 20 cover the whole catalog: after the penalty, cooking may fall off a single page of 8
    items = feed(client, "u1", sid, n=20)["items"] + feed(client, "u1", sid, n=20)["items"]
    cooking = [i for i in items if "cooking" in i["topics"]]
    assert len(cooking) == 9, "15 cooking videos minus the 6 already seen"
    assert all(i["breakdown"]["fatigue"] < -0.9 for i in cooking)
    assert all(i["breakdown"]["fatigue"] == 0 for i in items if "cooking" not in i["topics"])


def test_cold_user_gets_probe_items_across_contrasting_topics(client):
    seed_catalog(client, per_topic=10, topics=("cooking", "art", "music", "science"))
    items = feed(client, "brand-new", new_session_id(), n=8)["items"]
    first_four = [next(iter(i["topics"])) for i in items[:4]]
    assert len(set(first_four)) == 4, first_four
    assert all(i["slot"] == "probe" for i in items[:4])


def test_feed_n_is_bounded(client):
    seed_catalog(client)
    assert client.get("/feed", params={"user_id": "u", "session_id": new_session_id(), "n": 0}).status_code == 422
    assert client.get("/feed", params={"user_id": "u", "session_id": new_session_id(), "n": 50}).status_code == 422


# ----------------------------------------------------------------------------- events

def test_events_are_stored_append_only_and_update_the_profile(client, app, db):
    from api.db.models import Event

    cat = seed_catalog(client, per_topic=3)
    sid = new_session_id()
    out = post_events(client, "u1", sid, [watch(cat["cooking"][0], 1.0), watch(cat["art"][0], 0.05, kind="swipe")])
    assert out["accepted"] == 2
    assert db.query(Event).count() == 2

    uid = client.post("/users", json={"device_id": "u1"}).json()["user_id"]
    topics = app.state.profiles.topics(uid, now=time.time())
    assert topics["cooking"] > 0 > topics["art"]


def test_events_for_unknown_video_are_rejected(client):
    r = client.post("/events", json={"user_id": "u1", "session_id": new_session_id(),
                                     "events": [{"video_id": 999, "kind": "watch", "watch_ms": 10}]})
    assert r.status_code == 404


def test_session_keeps_only_the_last_20_events_with_a_30_minute_ttl(client, app, redis_client):
    cat = seed_catalog(client, per_topic=9)
    sid = new_session_id()
    vids = cat["cooking"] + cat["art"] + cat["music"]
    post_events(client, "u1", sid, [watch(v, 0.8, position=i) for i, v in enumerate(vids[:25])])
    state = app.state.sessions.load(sid)
    assert len(state.events) == 20
    assert state.events[-1].video_id == vids[24]["video_id"], "chronological, newest last"
    assert 1700 < redis_client.ttl(f"session:{sid}:events") <= 1800


# ----------------------------------------------------------------------------- trail

def trail(client, user_id: str, **params) -> list[dict]:
    r = client.get("/me/trail", params={"user_id": user_id, **params})
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_a_session_with_a_completion_always_leaves_a_trail(client):
    cat = seed_catalog(client, per_topic=3)
    sid = new_session_id()
    post_events(client, "u1", sid, [watch(cat["cooking"][0], 0.4, kind="swipe"), watch(cat["cooking"][1], 0.95)])
    kinds = {t["kind"] for t in trail(client, "u1", session_id=sid)}
    assert "streak" in kinds


def test_a_session_without_completions_leaves_no_streak(client):
    cat = seed_catalog(client, per_topic=3)
    sid = new_session_id()
    post_events(client, "u1", sid, [watch(v, 0.4, kind="swipe") for v in cat["cooking"]])
    assert trail(client, "u1", session_id=sid) == []


def test_save_series_and_first_completion_are_recorded(client):
    ep1 = create_video(client, "science", series_id=42, series_index=0)
    other = create_video(client, "science")
    sid = new_session_id()
    out = post_events(client, "u1", sid, [watch(ep1, 0.8), watch(other, 1.0, kind="save")])
    kinds = {t["kind"] for t in out["trail"]}
    assert {"series_progress", "saved", "topic_unlocked", "streak"} <= kinds
    series = next(t for t in out["trail"] if t["kind"] == "series_progress")
    assert series["ref_id"] == 42 and series["payload"]["index"] == 0


def test_streak_counts_completions_per_session(client):
    cat = seed_catalog(client, per_topic=4)
    sid = new_session_id()
    post_events(client, "u1", sid, [watch(v, 1.0, position=i) for i, v in enumerate(cat["cooking"])])
    streaks = [t for t in trail(client, "u1", session_id=sid) if t["kind"] == "streak"]
    assert len(streaks) == 1 and streaks[0]["payload"]["completions"] == 4


def test_streak_counts_each_video_once(client):
    v = create_video(client, "cooking")
    sid = new_session_id()
    post_events(client, "u1", sid, [watch(v, 1.0), watch(v, 1.0, kind="save"), watch(v, 1.1, kind="rewatch")])
    streak = next(t for t in trail(client, "u1", session_id=sid) if t["kind"] == "streak")
    assert streak["payload"] == {"completions": 1, "video_ids": [v["video_id"]]}


def test_series_progress_feeds_the_next_episode_first(client):
    seed_catalog(client, per_topic=5)
    ep0 = create_video(client, "science", series_id=9, series_index=0)
    ep1 = create_video(client, "science", series_id=9, series_index=1)
    post_events(client, "u1", new_session_id(), [watch(ep0, 0.9)])
    items = feed(client, "u1", new_session_id(), n=8)["items"]
    assert items[0]["video_id"] == ep1["video_id"] and items[0]["slot"] == "series"


def test_trail_is_scoped_to_the_user(client):
    cat = seed_catalog(client, per_topic=2)
    post_events(client, "u1", new_session_id(), [watch(cat["cooking"][0], 1.0)])
    assert trail(client, "u1") and trail(client, "u2") == []


# ----------------------------------------------------------------------------- UGC compliance: report / block

def test_reported_video_disappears_from_the_reporters_feed(client):
    seed_catalog(client, per_topic=4)
    bad = create_video(client, "cooking")
    r = client.post(f"/videos/{bad['video_id']}/report", json={"user_id": "u1", "reason": "harassment"})
    assert r.status_code == 200 and r.json()["hidden"] is True
    for _ in range(3):
        ids = {i["video_id"] for i in feed(client, "u1", new_session_id(), n=8)["items"]}
        assert bad["video_id"] not in ids
    assert bad["video_id"] in {i["video_id"] for i in feed(client, "u2", new_session_id(), n=20)["items"]}


def test_report_requires_a_known_reason(client):
    v = create_video(client, "cooking")
    assert client.post(f"/videos/{v['video_id']}/report", json={"user_id": "u1", "reason": "meh"}).status_code == 422
    assert client.post("/videos/999999/report", json={"user_id": "u1", "reason": "spam"}).status_code == 404


def test_blocked_creators_videos_are_hidden_from_the_blocker(client):
    creator = client.post("/users", json={"device_id": "creator-1"}).json()["user_id"]
    theirs = [client.post("/videos", json={"duration_ms": 9000, "topics": {"art": 1}, "creator_id": str(creator)}).json()
              for _ in range(3)]
    for v in theirs:
        client.put(v["upload_url"], content=b"x")
    others = seed_catalog(client, per_topic=4)
    r = client.post("/users/block", json={"user_id": "u1", "blocked_user_id": creator})
    assert r.status_code == 200
    ids = {i["video_id"] for i in feed(client, "u1", new_session_id(), n=20)["items"]}
    assert not ({v["video_id"] for v in theirs} & ids) and ids
    assert client.post("/users/block", json={"user_id": "u1", "blocked_user_id": creator}).status_code == 200, "idempotent"
