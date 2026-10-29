from datetime import date

from unseenet.known_nodes import KnownNode

from unseenet_stats import network
from unseenet_stats.aggregate import Seen


def test_canary_counts_what_reached_every_node():
    a = [("<1>", "canary node1 2026-10-28"), ("<2>", "canary node2 2026-10-28"),
         ("<0>", "canary node1 2026-10-27")]
    b = [("<1>", "canary node1 2026-10-28")]                  # node2's never got here
    c = network.canary([a, b], date(2026, 10, 29))
    assert c == {"date": "2026-10-28", "posted": 2, "everywhere": 1}


def test_nodes_tell_own_from_others_and_only_totals():
    own = [KnownNode("unseenet-node1", "a" * 56)]
    listed = own + [KnownNode("kvist", "b" * 56)]
    infos = [{"software": "unseenet 0.6.1", "policy": {"blobs": {"encrypted": True}, "sites": "accept",
                                                        "retention_days": 90}},
             {"software": "unseenet 0.6.0", "policy": {"retention_days": 30}}]
    n = network.nodes(listed, own, infos, "0.6.1")
    assert n["list"] == [{"name": "unseenet-node1", "project": True}, {"name": "kvist", "project": False}]
    assert (n["project"], n["others"], n["on_stable"]) == (1, 1, 1)
    assert n["policies"]["files"] == 1 and n["policies"]["encrypted_files"] == 1
    assert n["policies"]["retention_days"] == [30, 90]
    assert "a" * 56 not in str(n)                               # names only, no addresses


def test_demo_people_are_thread_starters_in_the_demo():
    d = date(2026, 10, 28)
    arts = [Seen(d, "unseenet.demo.feed@lcgptqqjydt2sevj", "feed", "demo1"),
            Seen(d, "unseenet.demo.feed@lcgptqqjydt2sevj", "comment", "visitor", reply=True),
            Seen(d, "alt.a@aaaaaaaaaaaaaaaa", "post", "someone")]
    assert network.demo_keys(arts) == {"demo1"}


def test_entrances_without_a_list():
    assert network.entrances([], set(), check=False) == {"listed": 0, "list": []}
