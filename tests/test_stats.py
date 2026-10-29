from datetime import date, datetime, timezone

from unseenet_stats.aggregate import Crawl, Seen, build, merge_days
from unseenet.core import crypto
from unseenet.core.crypto import Identity

from unseenet_stats.classify import GroupInfo, category, system_part

OWNER = "ed25519:owner"
OTHER = "ed25519:other"


def g(gid="alt.test@aaaaaaaaaaaaaaaa", **kw):
    return GroupInfo(gid, known=True, **kw)


def test_kinds():
    assert category({"message-kind": "chat"}, g()) == "chat"
    assert category({"message-kind": "post"}, g()) == "post"
    assert category({}, g()) == "post"                       # no header: a post
    assert category({"message-kind": " CHAT "}, g()) == "chat"


def test_hidden_and_housekeeping():
    assert category({"control": "manifest"}, g()) == "system"
    assert category({"encrypted": "xchacha20poly1305; epoch=1"}, g(type="closed")) == "closed"
    assert category({"encrypted": "sealedbox"}, g("inbox@aaaaaaaaaaaaaaaa")) == "private"
    assert category({"message-kind": "chat"}, g("x@aaaaaaaaaaaaaaaa", view="data")) == "system"
    assert category({}, g("profile@aaaaaaaaaaaaaaaa")) == "system"
    assert category({"origin-network": "usenet"}, g()) == "imported"


def test_comments_and_feeds():
    ch = g(type="channel", starters=frozenset({OWNER}))
    assert category({"author-key": OWNER}, ch) == "post"
    assert category({"author-key": OTHER, "references": "<a@unseenet>"}, ch) == "comment"
    assert category({"author-key": OWNER, "references": "<a@unseenet>"}, ch) == "post"
    feed = g(type="channel", view="feed", starters=frozenset({OWNER}))
    assert category({"author-key": OWNER}, feed) == "feed"
    assert category({"author-key": OTHER, "references": "<a@unseenet>"}, feed) == "comment"


def test_counts_never_go_down():
    old = [{"date": "2026-10-01", "categories": {"post": 5}, "keys": 3}]
    new = {"2026-10-01": {"categories": {"post": 2, "chat": 1}, "keys": 1},
           "2026-10-02": {"categories": {"post": 1}, "keys": 1},
           "2030-01-01": {"categories": {"post": 1}, "keys": 1}}
    days = merge_days(old, new, date(2026, 10, 2))
    assert days == [{"date": "2026-10-01", "categories": {"post": 5, "chat": 1}, "keys": 3},
                    {"date": "2026-10-02", "categories": {"post": 1}, "keys": 1}]


def test_build_counts_only_people_in_the_open():
    c = Crawl(started=datetime(2026, 10, 19, 8, tzinfo=timezone.utc))
    c.groups = {"alt.a@aaaaaaaaaaaaaaaa": g("alt.a@aaaaaaaaaaaaaaaa"),
                "inbox@bbbbbbbbbbbbbbbb": g("inbox@bbbbbbbbbbbbbbbb", type="inbox")}
    d = date(2026, 10, 18)
    c.articles = {
        "<1>": Seen(d, "alt.a@aaaaaaaaaaaaaaaa", "post", "k1"),
        "<2>": Seen(d, "alt.a@aaaaaaaaaaaaaaaa", "chat", "k2"),
        "<3>": Seen(d, "inbox@bbbbbbbbbbbbbbbb", "private", "k3"),
        "<4>": Seen(d, "alt.a@aaaaaaaaaaaaaaaa", "imported", "gw", "usenet"),
    }
    s = build(c)
    assert s["keys"]["active_7"] == 2
    assert s["keys"]["inboxes"] == 1
    assert s["groups"]["total"] == 1
    assert s["gateways"] == {"usenet": {"articles": 1, "gateways": 1, "groups": 1}}
    assert "k1" not in str(s)                                  # no keys in the output


def test_personal_feeds_and_sites():
    me = Identity.generate()
    key = crypto.key_to_text(me.public_key)
    fp = crypto.fingerprint(me.public_key)
    feed = GroupInfo(f"feed@{fp}")
    site = GroupInfo(f"site@{fp}")
    assert (feed.type, feed.view) == ("channel", "feed")
    assert category({"author-key": key}, feed) == "feed"
    assert category({"author-key": OTHER, "references": "<a@unseenet>"}, feed) == "comment"
    assert category({"author-key": key, "references": "<a@unseenet>"}, feed) == "feed"
    assert category({"author-key": key}, site) == "page"
    assert category({}, GroupInfo(f"ripe@{fp}")) == "system"


def test_reactions_edits_pages():
    feed = g(type="channel", view="feed", starters=frozenset({OWNER}))
    assert category({"message-kind": "reaction", "author-key": OTHER, "references": "<a@x>"}, feed) == "reaction"
    assert category({"author-key": OWNER, "supersedes": "<a@x>"}, feed) == "edit"
    assert category({"author-key": OWNER}, g(type="channel", view="pages", starters=frozenset({OWNER}))) == "page"


def test_system_parts():
    fp = "aaaaaaaaaaaaaaaa"
    assert system_part({}, GroupInfo(f"ripe@{fp}")) == "ripening"
    assert system_part({}, GroupInfo(f"avatar@{fp}")) == "profiles"
    assert system_part({}, GroupInfo(f"labels@{fp}")) == "reports"
    assert system_part({"control": "manifest"}, g()) == "control"
    assert system_part({}, g("unseenet.nodes@" + fp, view="data")) == "lists"


def test_reactions_do_not_make_keys_active():
    c = Crawl(started=datetime(2026, 10, 29, 8, tzinfo=timezone.utc))
    c.groups = {"alt.a@aaaaaaaaaaaaaaaa": g("alt.a@aaaaaaaaaaaaaaaa")}
    d = date(2026, 10, 28)
    c.articles = {"<1>": Seen(d, "alt.a@aaaaaaaaaaaaaaaa", "post", "k1"),
                  "<2>": Seen(d, "alt.a@aaaaaaaaaaaaaaaa", "reaction", "k2")}
    assert build(c)["keys"]["active_7"] == 1


def test_older_file_is_counted_again():
    c = Crawl(started=datetime(2026, 10, 29, 8, tzinfo=timezone.utc))
    c.groups = {"alt.a@aaaaaaaaaaaaaaaa": g("alt.a@aaaaaaaaaaaaaaaa")}
    c.articles = {"<1>": Seen(date(2026, 10, 28), "alt.a@aaaaaaaaaaaaaaaa", "feed", "k1")}
    old = {"v": 1, "days": [{"date": "2026-10-01", "categories": {"post": 4}, "keys": 2},
                            {"date": "2026-10-28", "categories": {"system": 9}, "keys": 0}]}
    days = build(c, old)["days"]
    assert days[0]["categories"] == {"post": 4}                 # no longer on the nodes: kept
    assert days[1]["categories"] == {"feed": 1}                 # seen again: counted anew
