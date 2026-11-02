"""Councils on the stats page (#18): counted from the members' own copies, and who keeps
what - the registrar once the project key has said it moved."""
from datetime import datetime, timedelta, timezone

from unseenet.core import council as cn, crypto
from unseenet.core.groups import manifest_article
from unseenet.names import MOVED_TO

from unseenet_stats import network

NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
DAY = NOW.replace(hour=0)


def _council(name="unseenet.names", n=3, founder=None):
    ids = [crypto.Identity.generate() for _ in range(n)]
    members = [cn.Member(i.public_key, DAY, True) for i in ids]
    founding = cn.Founding(founder.public_key, DAY + timedelta(days=3 * 365), 9) if founder else None
    body = cn.council_body(name, "channel", seq=1, date=DAY, members=members, min_level=3,
                           founding=founding)
    gid = cn.make_council_group_id(name, body)
    return ids, gid, [cn.council_article(i, gid, body, pow_bits=1, now=NOW) for i in ids]


def _moved(owner, to):
    data = {"v": 1, "name": "unseenet.names", "type": "channel", "serial": 9,
            "owner": owner.key_text, MOVED_TO: to}
    return manifest_article(owner, f"unseenet.names@{crypto.fingerprint(owner.public_key)}",
                            data, pow_bits=1, now=NOW)


def test_a_council_counts_only_when_every_founder_posted():
    founder = crypto.Identity.generate()
    ids, gid, copies = _council(founder=founder)
    assert network.councils(copies[:2], NOW)["list"] == []
    [c] = network.councils(copies, NOW)["list"]
    assert c["group"] == gid and (c["members"], c["full"], c["quorum"]) == (3, 3, 2)
    assert c["founding_until"] == "2029-11-01" and c["min_level"] == 3 and not c["disputed"]
    assert c["keeps"] == ""


def test_its_own_groups_are_not_councils_of_their_own():
    _, _, copies = _council("unseenet.names.talk")
    assert network.councils(copies, NOW)["list"] == []


def test_the_registrar_moves_only_on_the_project_keys_word(monkeypatch):
    project, someone = crypto.Identity.generate(), crypto.Identity.generate()
    monkeypatch.setattr(network, "PROJECT_KEY", project.key_text)
    monkeypatch.setattr(network, "REGISTRAR",
                        f"unseenet.names@{crypto.fingerprint(project.public_key)}")
    _, gid, copies = _council()
    assert network.registrar_moved_to([_moved(someone, gid)]) is None
    assert network.registrar_moved_to([_moved(project, gid)]) == gid
    got = network.councils(copies + [_moved(project, gid)], NOW)
    assert got["list"][0]["keeps"] == "names"
    assert got["keepers"]["names"] == gid and got["keepers"]["nodes"] == "the project key"
    # a move to a council that does not count leaves the names with the project key
    assert network.councils(copies[:2] + [_moved(project, gid)], NOW)["keepers"]["names"] \
        == "the project key"
