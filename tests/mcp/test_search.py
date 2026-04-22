from pathlib import Path
import pytest
from claude_hub.mcp.search import Match, search_conversations


def test_empty_query_raises(tmp_claude_home: Path):
    with pytest.raises(ValueError):
        search_conversations("", claude_home=tmp_claude_home)


def test_no_matches_returns_empty(tmp_claude_home: Path, make_jsonl):
    make_jsonl(
        "-a",
        cwd="/a",
        lines=[
            {"type": "user", "message": {"role": "user", "content": "hello world"}, "timestamp": "2026-01-01T00:00:00Z"},
        ],
    )
    assert search_conversations("supabase", claude_home=tmp_claude_home) == []


def test_finds_substring_in_user_content_str(tmp_claude_home: Path, make_jsonl):
    make_jsonl(
        "-a",
        cwd="/a",
        lines=[
            {
                "type": "user",
                "message": {"role": "user", "content": "we use supabase auth here"},
                "timestamp": "2026-01-01T00:00:00Z",
                "sessionId": "s1",
            },
        ],
    )
    res = search_conversations("supabase", claude_home=tmp_claude_home)
    assert len(res) == 1
    assert res[0].project_path == "/a"
    assert res[0].session_id == "s1"
    assert "supabase" in res[0].snippet.lower()
    assert res[0].match_count == 1


def test_finds_substring_in_assistant_content_blocks(tmp_claude_home: Path, make_jsonl):
    make_jsonl(
        "-b",
        cwd="/b",
        lines=[
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "You can use Stripe for that."},
                        {"type": "tool_use", "name": "Bash", "input": {"cmd": "ls"}},
                    ],
                },
                "timestamp": "2026-01-02T00:00:00Z",
                "sessionId": "s2",
            },
        ],
    )
    res = search_conversations("stripe", claude_home=tmp_claude_home)
    assert len(res) == 1
    assert res[0].session_id == "s2"


def test_case_insensitive_by_default(tmp_claude_home: Path, make_jsonl):
    make_jsonl(
        "-c",
        cwd="/c",
        lines=[
            {
                "type": "user",
                "message": {"role": "user", "content": "SUPABASE is cool"},
                "timestamp": "2026-01-01T00:00:00Z",
                "sessionId": "s3",
            },
        ],
    )
    res = search_conversations("supabase", claude_home=tmp_claude_home)
    assert len(res) == 1


def test_case_sensitive_flag(tmp_claude_home: Path, make_jsonl):
    make_jsonl(
        "-d",
        cwd="/d",
        lines=[
            {
                "type": "user",
                "message": {"role": "user", "content": "SUPABASE is cool"},
                "timestamp": "2026-01-01T00:00:00Z",
                "sessionId": "s4",
            },
        ],
    )
    res = search_conversations("supabase", case_sensitive=True, claude_home=tmp_claude_home)
    assert res == []


def test_groups_by_session_counts_hits(tmp_claude_home: Path, make_jsonl):
    make_jsonl(
        "-e",
        cwd="/e",
        lines=[
            {
                "type": "user",
                "message": {"role": "user", "content": "redis is redis"},
                "timestamp": "2026-01-01T00:00:00Z",
                "sessionId": "s5",
            },
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "more redis talk"}]},
                "timestamp": "2026-01-01T00:00:01Z",
                "sessionId": "s5",
            },
        ],
    )
    res = search_conversations("redis", claude_home=tmp_claude_home)
    assert len(res) == 1
    # 2 hits in first line + 1 in second line = 3 hits total
    assert res[0].match_count == 3


def test_sorted_by_timestamp_desc(tmp_claude_home: Path, make_jsonl):
    make_jsonl(
        "-x",
        cwd="/x",
        lines=[
            {"type": "user", "message": {"role": "user", "content": "k8s"}, "timestamp": "2026-01-01T00:00:00Z", "sessionId": "old"},
        ],
    )
    make_jsonl(
        "-y",
        cwd="/y",
        lines=[
            {"type": "user", "message": {"role": "user", "content": "k8s"}, "timestamp": "2026-01-05T00:00:00Z", "sessionId": "new"},
        ],
    )
    res = search_conversations("k8s", claude_home=tmp_claude_home)
    assert [r.session_id for r in res] == ["new", "old"]


def test_limit_respected(tmp_claude_home: Path, make_jsonl):
    for i in range(5):
        make_jsonl(
            f"-p{i}",
            cwd=f"/p{i}",
            lines=[
                {"type": "user", "message": {"role": "user", "content": "foo"}, "timestamp": f"2026-01-0{i+1}T00:00:00Z", "sessionId": f"s{i}"},
            ],
        )
    res = search_conversations("foo", limit=3, claude_home=tmp_claude_home)
    assert len(res) == 3


def test_skips_malformed_jsonl_lines(tmp_claude_home: Path, tmp_path: Path):
    # Create a jsonl with one bad line and one good line
    proj = tmp_claude_home / "projects" / "-z"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text(
        'not json\n{"type":"user","message":{"role":"user","content":"needle"},"timestamp":"2026-01-01T00:00:00Z","sessionId":"sx","cwd":"/z"}\n',
        encoding="utf-8",
    )
    res = search_conversations("needle", claude_home=tmp_claude_home)
    assert len(res) == 1
    assert res[0].session_id == "sx"


def test_snippet_contains_match_with_context(tmp_claude_home: Path, make_jsonl):
    long = "A" * 200 + " NEEDLE " + "B" * 200
    make_jsonl(
        "-n",
        cwd="/n",
        lines=[
            {
                "type": "user",
                "message": {"role": "user", "content": long},
                "timestamp": "2026-01-01T00:00:00Z",
                "sessionId": "sn",
            },
        ],
    )
    res = search_conversations("needle", claude_home=tmp_claude_home)
    assert len(res) == 1
    s = res[0].snippet
    assert "NEEDLE" in s.upper()
    # snippet must not be the entire text — it's bounded
    assert len(s) < 300
