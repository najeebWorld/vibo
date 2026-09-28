"""Creator feedback: a video's retention curve from live events, plus the creator's video list."""
from __future__ import annotations

import pytest

from tests.conftest import create_video, new_session_id, post_events, watch


def curve(client, video_id: int) -> dict:
    r = client.get(f"/videos/{video_id}/retention")
    assert r.status_code == 200, r.text
    return r.json()


def test_retention_curve_and_histogram_from_watch_ratios(client):
    v = create_video(client, "cooking", duration_ms=10_000)
    ratios = [0.05, 0.15, 0.15, 0.55, 0.95, 1.0, 1.2]        # 7 views; 1.2 = rewatch, counts as complete
    for i, r in enumerate(ratios):
        kind = "swipe" if r < 0.5 else ("rewatch" if r > 1 else "watch")
        post_events(client, f"u{i}", new_session_id(), [watch(v, r, kind=kind)])
    post_events(client, "u9", new_session_id(), [{"video_id": v["video_id"], "kind": "impression"}])

    c = curve(client, v["video_id"])
    assert c["views"] == 7
    assert c["histogram"] == [1, 2, 0, 0, 0, 1, 0, 0, 0, 3]          # 10 buckets of 10%
    assert c["retention"] == pytest.approx([1.0, 6 / 7, 4 / 7, 4 / 7, 4 / 7, 4 / 7, 3 / 7, 3 / 7, 3 / 7, 3 / 7, 2 / 7])  # 0.95 < 100%
    assert c["completion_rate"] == pytest.approx(3 / 7)
    assert c["biggest_drop"] == {"at_pct": 10, "lost_share": pytest.approx(2 / 7)}
    assert c["duration_ms"] == 10_000 and c["age_s"] >= 0


def test_retention_curve_is_live_not_waiting_for_the_stats_fold(client):
    v = create_video(client, "cooking")
    assert curve(client, v["video_id"])["views"] == 0
    post_events(client, "u1", new_session_id(), [watch(v, 1.0)])
    assert curve(client, v["video_id"])["views"] == 1


def test_empty_video_has_flat_curve(client):
    v = create_video(client, "cooking")
    c = curve(client, v["video_id"])
    assert c["histogram"] == [0] * 10 and c["retention"] == [0.0] * 11
    assert c["completion_rate"] == 0.0 and c["biggest_drop"] is None


def test_unknown_video_is_404(client):
    assert client.get("/videos/424242/retention").status_code == 404


def test_my_videos_lists_only_my_uploads_newest_first(client):
    me = client.post("/users", json={"device_id": "me"}).json()["user_id"]
    mine = [client.post("/videos", json={"duration_ms": 8000, "topics": {"diy": 1}, "creator_id": "me"}).json() for _ in range(2)]
    create_video(client, "art")   # someone else's
    post_events(client, "u1", new_session_id(), [{"video_id": mine[1]["video_id"], "kind": "watch", "watch_ms": 8000}])

    r = client.get("/me/videos", params={"user_id": "me"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["video_id"] for i in items] == [mine[1]["video_id"], mine[0]["video_id"]]
    assert items[0]["views"] == 1 and items[0]["completion_rate"] == 1.0 and items[1]["views"] == 0
    assert all(i["creator_id"] == me for i in items)
