"""Councils on the stats page (#18): counted from the members' own copies, and who keeps
what - the registrar once the project key has said it moved."""
from datetime import datetime, timedelta, timezone

from unseenet.core import council as cn, crypto
from unseenet.core.groups import manifest_article
from unseenet.names import MOVED_TO

from unseenet_stats import network

NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
DAY = NOW.replace(hour=0)


CLAIMS = "unseenet.names.claims@cpphmdeq57oz4omb"


def _council(name="unseenet.names", n=3, founder=None, ids=None, fields=None):
    ids = ids or [crypto.Identity.generate() for _ in range(n)]
    members = [cn.Member(i.public_key, DAY, True) for i in ids]
    founding = cn.Founding(founder.public_key, DAY + timedelta(days=3 * 365), 9) if founder else None
    if fields is None:
        fields = {"claims": CLAIMS} if name == "unseenet.names" else {}
    body = cn.council_body(name, "channel", seq=1, date=DAY, members=members, min_level=3,
                           founding=founding, fields=fields)
    gid = cn.make_council_group_id(name, body)
    return ids, gid, [cn.council_article(i, gid, body, pow_bits=1, now=NOW) for i in ids]


def _moved(owner, to, name="unseenet.names"):
    data = {"v": 1, "name": name, "type": "channel", "serial": 9,
            "owner": owner.key_text, MOVED_TO: to}
    return manifest_article(owner, f"{name}@{crypto.fingerprint(owner.public_key)}",
                            data, pow_bits=1, now=NOW)


def test_a_council_counts_only_when_every_founder_posted():
    founder = crypto.Identity.generate()
    ids, gid, copies = _council(founder=founder)
    assert network.councils(copies[:2], NOW)["list"] == []
    [c] = network.councils(copies, NOW)["list"]
    assert c["group"] == gid and (c["members"], c["full"], c["quorum"]) == (3, 3, 2)
    assert c["founding_until"] == "2029-11-01" and c["min_level"] == 3 and not c["disputed"]
    assert c["keeps"] == [] and c["parts"][0]["role"] == "name claims"


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
    assert got["list"][0]["keeps"] == ["names"]
    assert got["keepers"]["names"] == gid and got["keepers"]["nodes"] == "the project key"
    # a move to a council that does not count leaves the names with the project key
    assert network.councils(copies[:2] + [_moved(project, gid)], NOW)["keepers"]["names"] \
        == "the project key"


def test_a_list_council_is_one_council_with_its_groups(monkeypatch):
    """UN-RFC 0020 section 4: the list council's list groups, reports and claims are
    council groups of the same members - shown under the council, not as councils of
    their own. A group of the same members that no council names yet waits apart."""
    project = crypto.Identity.generate()
    monkeypatch.setattr(network, "PROJECT_KEY", project.key_text)
    old_nodes = f"unseenet.nodes@{crypto.fingerprint(project.public_key)}"
    monkeypatch.setattr(network, "OLD_GROUPS", {**network.OLD_GROUPS, "nodes": old_nodes})
    ids = [crypto.Identity.generate() for _ in range(3)]
    arts = []
    groups = {}
    for name in ("unseenet.nodes", "unseenet.lists.reports", "unseenet.lists.claims",
                 "unseenet.hierarchies"):
        _, groups[name], copies = _council(name, ids=ids)
        arts += copies
    fields = {"lists": {"nodes": groups["unseenet.nodes"]},
              "reports": groups["unseenet.lists.reports"],
              "claims": groups["unseenet.lists.claims"]}
    _, lists, copies = _council("unseenet.lists", ids=ids, fields=fields)
    arts += copies
    got = network.councils(arts, NOW)
    [c] = got["list"]
    assert c["group"] == lists and c["keeps"] == [] and c["takes_on"] == ["nodes"]
    roles = {p["group"]: p["role"] for p in c["parts"]}
    assert roles == {groups["unseenet.nodes"]: "the list of nodes",
                     groups["unseenet.lists.reports"]: "measurements (reports)",
                     groups["unseenet.lists.claims"]: "hierarchy claims"}
    assert all(p["counts"] and p["in_step"] and not p["moved"] for p in c["parts"])
    [w] = got["waiting"]
    assert w["group"] == groups["unseenet.hierarchies"] and w["same_as"] == [lists]
    assert got["keepers"]["nodes"] == "the project key"
    # once the project key moves the node list, the council keeps it
    got = network.councils(arts + [_moved(project, lists, "unseenet.nodes")], NOW)
    [c] = got["list"]
    assert got["keepers"]["nodes"] == lists and c["keeps"] == ["nodes"] and c["takes_on"] == []
    assert [p["moved"] for p in c["parts"] if p["kind"] == "nodes"] == [True]
