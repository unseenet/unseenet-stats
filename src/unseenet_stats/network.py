"""The network's own lists, read from its data groups: what is released, which nodes,
entrances and gateways there are, the hierarchies, the canaries - and which keys are
bots or demo people, so active keys can also be told without them.

Everything here comes from signed articles any reader can fetch, and only totals,
names the lists themselves publish and versions are put in the published numbers.
Nothing is taken from GitHub.
"""

from __future__ import annotations

import logging
import re
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

from unseenet.core import crypto, gateways
from unseenet.core.article import Article, ArticleError, parse_date
from unseenet.core.groups import Manifest, split_group_id
from unseenet.core.profiles import profile_from_manifest
from unseenet.names import MOVED_TO, NAMES_GROUP
from unseenet.hierarchies import HIERARCHIES_GROUP, parse_hierarchy_list, parse_root_list
from unseenet.known_nodes import (CANARY_GROUP, ENTRANCES_GROUP, NODES_GROUP, PROJECT_KEY,
                                  RELEASES_GROUP, parse_entrance_list, parse_node_list)
from unseenet.update import UpdateError, check_signature, parse_release_post

log = logging.getLogger("unseenet-stats")

DIRECTORY_GROUP = gateways.DIRECTORY_GROUP
DEMO_HIERARCHY = "unseenet.demo."
# Data groups whose newest articles are fetched whole, and how many of them.
FETCH_NEWEST = {RELEASES_GROUP: 60, ENTRANCES_GROUP: 6, DIRECTORY_GROUP: 50,
                HIERARCHIES_GROUP: 6, NODES_GROUP: 10}
# Groups whose Subject the crawler asks for with HDR (besides the names group).
SUBJECT_GROUPS = (CANARY_GROUP,)
_VERSION = re.compile(r"^Unseenet (?P<version>[0-9][0-9A-Za-z.+]*), (?P<channel>stable|dev)$")
_CANARY = re.compile(r"^canary (?P<node>\S+) (?P<day>\d{4}-\d\d-\d\d)$")


def _date(art: Article):
    try:
        return parse_date(art.get("Date", ""))
    except (TypeError, ValueError):
        return None


def newest_valid(arts: list[Article], group: str, allowed: set[str], parse):
    """(Date, parsed) of the newest article in ``group`` by an allowed key that ``parse``
    accepts; None if there is none."""
    best = None
    for art in arts:
        if art.group != group or art.control or art.get("Author-Key") not in allowed:
            continue
        try:
            value = parse(art.body)
        except (ValueError, TypeError, KeyError):
            continue
        d = _date(art)
        if d and (best is None or d > best[0]):
            best = (d, value)
    return best


# ---------------------------------------------------------------- releases (#12)

def releases(arts: list[Article]) -> dict:
    """The newest signed release of each channel in unseenet.releases (UN-RFC 0043 7.3).
    Only posts whose checksums are signed by a key trusted for their channel count."""
    out: dict[str, dict] = {}
    for art in arts:
        if art.group != RELEASES_GROUP or art.control:
            continue
        parsed = parse_release_post(art.body)
        head = _VERSION.match(art.body.split("\n", 1)[0].strip())
        if not parsed or not head:
            continue
        channel, sums, sig = parsed
        try:
            key = check_signature(sums, sig, channel)
        except (UpdateError, ValueError):
            continue
        d = _date(art)
        if d is None:
            continue
        cur = out.get(channel)
        if cur is None or d.isoformat() > cur["_d"]:
            out[channel] = {"version": head["version"], "date": d.date().isoformat(),
                            "signed_by": "project key" if key == PROJECT_KEY else "release key",
                            "_d": d.isoformat()}
    for v in out.values():
        v.pop("_d")
    return out


# ------------------------------------------------------------------- nodes (#13)

def nodes(listed: list, builtin: list, infos: list[dict], stable: str | None) -> dict:
    """Names from the node list, which are the project's own (the built-in list's), and
    totals from the reached nodes' NODEINFO. Never which node answered: a daily record
    of that is a record of each onion service's uptime."""
    own = {n.address for n in builtin}
    names = [{"name": n.name or n.address[:16], "project": n.address in own}
             for n in sorted(listed, key=lambda n: (n.address not in own, n.name))]
    pol = [i.get("policy", {}) or {} for i in infos]
    blobs = [p.get("blobs") for p in pol if p.get("blobs")]
    retention = sorted(p.get("retention_days") for p in pol
                       if isinstance(p.get("retention_days"), int))
    software = [str(i.get("software", "")) for i in infos]
    return {
        "list": names,
        "project": sum(1 for n in names if n["project"]),
        "others": sum(1 for n in names if not n["project"]),
        "policies": {
            "files": len(blobs),
            "encrypted_files": sum(1 for b in blobs if b.get("encrypted")),
            "sites": sum(1 for p in pol if p.get("sites") == "accept"),
            "profiles": sum(1 for p in pol if p.get("profiles") == "accept"),
            "pictures": sum(1 for p in pol if p.get("avatars") == "accept"),
            "follow_reports": sum(1 for p in pol if p.get("report_issuers")),
            "retention_days": [retention[0], retention[-1]] if retention else [],
        },
        "on_stable": sum(1 for s in software if stable and s == f"unseenet {stable}"),
    }


# ------------------------------------------------- gateways and entrances (#14)

def gateway_directory(arts: list[Article], now: datetime) -> list[dict]:
    """The gateways announcing themselves in the directory (UN-RFC 0038), newest
    announcement per gateway key; no operator names, as for nodes."""
    out = []
    for a in gateways.current([x for x in arts if x.group == DIRECTORY_GROUP], now=now):
        out.append({"name": a.name, "groups": len(a.groups),
                    "networks": [{"network": n.network, "import": n.imports, "export": n.exports}
                                 for n in a.networks]})
    return out


def probe(url: str, timeout: float = 15) -> bool:
    """Whether a public https entrance answers right now. Public web servers only:
    onion-only entrances are not probed."""
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "unseenet-stats"})
        with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - https only
            return 200 <= r.status < 400
    except Exception:  # noqa: BLE001
        return False


def entrances(arts: list[Article], allowed: set[str], check: bool = True) -> dict:
    found = newest_valid(arts, ENTRANCES_GROUP, allowed, parse_entrance_list)
    if not found:
        return {"listed": 0, "list": []}
    updated, items = found[1]
    out = []
    for e in items:
        item = {"name": e["name"], "url": e["url"], "onion": bool(e["onion"])}
        if e["url"] and check:
            item["answers"] = probe(e["url"])
        out.append(item)
    return {"listed": len(out), "updated": updated, "list": out,
            "answering": sum(1 for e in out if e.get("answers"))}


# --------------------------------------------------- hierarchies, canary (#15)

def hierarchies(arts: list[Article], allowed: set[str]) -> dict:
    found = newest_valid(arts, HIERARCHIES_GROUP, allowed, parse_root_list)
    if not found:
        return {}
    updated, by_name = found[1]
    return {"total": len(by_name), "updated": updated,
            "by_policy": dict(Counter(h.policy for h in by_name.values()).most_common())}


def canary(subjects_per_node: list[list[tuple[str, str]]], today) -> dict:
    """Yesterday's canaries (UN-RFC 0021): how many nodes posted one, and how many of
    those reached every node that answered - whether the network is one network."""
    day = (today - timedelta(days=1)).isoformat()
    seen: dict[str, set[str]] = {}               # Message-ID -> node that posted it
    on: list[set[str]] = []
    for subjects in subjects_per_node:
        ids = set()
        for msgid, subject in subjects:
            m = _CANARY.match(subject.strip())
            if m and m["day"] == day:
                seen.setdefault(msgid, set()).add(m["node"])
                ids.add(msgid)
        on.append(ids)
    posted = {n for ns in seen.values() for n in ns}
    everywhere = {n for msgid, ns in seen.items() if on and all(msgid in s for s in on) for n in ns}
    return {"date": day, "posted": len(posted), "everywhere": len(everywhere)}


# --------------------------------------------------- bots and demo people (#16)

def bot_keys(profile_manifests: list[Article]) -> set[str]:
    """Keys whose public profile says they are a program (UN-RFC 0030 section 6)."""
    newest: dict[str, Manifest] = {}
    for art in profile_manifests:
        try:
            m = Manifest.from_article(art, stored=True)
        except ArticleError:
            continue
        if art.group not in newest or m.supersedes(newest[art.group]):
            newest[art.group] = m
    out = set()
    for m in newest.values():
        try:
            p = profile_from_manifest(m)
        except Exception:  # noqa: BLE001 - a malformed profile says nothing
            continue
        if p is not None and p.bot:
            out.add(crypto.key_to_text(p.key))
    return out


def demo_keys(seen_articles) -> set[str]:
    """The demo's people: keys that start threads in unseenet.demo.* (repliers there
    are visitors, not the demo)."""
    return {a.author for a in seen_articles
            if a.group_id.startswith(DEMO_HIERARCHY) and a.author and not a.reply}


# ------------------------------------------------- spam reports and labels

def governed(arts: list[Article], allowed: set[str]) -> dict[str, tuple[str, str]]:
    """{hierarchy: (its list's Group ID, its maintainer's key)} for the governed
    hierarchies of the newest root list (UN-RFC 0018)."""
    found = newest_valid(arts, HIERARCHIES_GROUP, allowed, parse_root_list)
    if not found:
        return {}
    return {name: (h.list, h.maintainer) for name, h in found[1][1].items()
            if h.policy == "governed" and h.list and h.maintainer}


def recommended(arts: list[Article], lists: dict[str, tuple[str, str]],
                posters=lambda group: set()) -> dict[str, list[str]]:
    """{issuer key: [hierarchies whose list names it]} - the issuers a hierarchy's
    maintainer names are followed there by default (UN-RFC 0045 7.1, 0053 5). The
    list is posted by the maintainer or a poster in its group's manifest."""
    out: dict[str, list[str]] = {}
    for name, (group, maintainer) in sorted(lists.items()):
        found = newest_valid(arts, group, {maintainer} | set(posters(group)),
                             lambda text, name=name: parse_hierarchy_list(text, name))
        if not found:
            continue
        hl = found[1]
        for key in (*hl.report_issuers, *hl.labellers):
            out.setdefault(key, []).append(name + ".*")
    return out


def issuers(manifests: list[Article], counts: dict[str, int], infos: list[dict],
            recommend: dict[str, list[str]]) -> list[dict]:
    """The spam-report issuers (reports@, UN-RFC 0045) and labellers (labels@, 0053)
    in the network, from their signed manifests: what they say they do, whether a
    program does it, how much they have published, how many of the answering nodes
    follow them, and which hierarchies name them. The key only as its fingerprint,
    and no contact - a reader decides by the policy, and reaches them in the network."""
    newest: dict[str, Manifest] = {}
    for art in manifests:
        try:
            m = Manifest.from_article(art, stored=True)
        except ArticleError:
            continue
        if art.group not in newest or m.supersedes(newest[art.group]):
            newest[art.group] = m
    followed = Counter(k for i in infos for k in ((i.get("policy") or {}).get("report_issuers") or []))
    out = []
    for gid, m in sorted(newest.items()):
        name, fp = split_group_id(gid)
        key = crypto.key_to_text(m.owner)
        raw = m.raw
        out.append({
            "kind": "labels" if name == "labels" else "reports",
            "title": str(raw.get("title", ""))[:80],
            "automatic": raw.get("automatic") is True,
            "policy": str(raw.get("policy", ""))[:400],
            "fingerprint": fp,
            "published": counts.get(gid, 0),
            "nodes_following": followed.get(key, 0),
            "recommended_for": recommend.get(key, []),
        })
    return out


# ---------------------------------------------------------------- councils (#18)

# A council is a set of keys that keeps something: a registrar (``claims``, UN-RFC 0054
# section 8) or lists (``lists``, UN-RFC 0020 section 4). Every other group it names -
# its list groups, reports, claims, announcement groups, proposals, talk, log and room -
# is a council group of the same members too, with a genesis of its own. Those are shown
# as parts of their council, not as councils of their own.
COUNCIL_PARTS = (".proposals", ".talk", ".log", ".claims", ".room", ".reports")
REGISTRAR = NAMES_GROUP                 # the project's registrar group (UN-RFC 0019)
# The project's old groups, by what they keep. Each moves to a council with a last
# manifest the project key signs, naming it in ``moved_to`` (UN-RFC 0054 section 14,
# UN-RFC 0020 section 10; the gateway directory names the new directory itself).
OLD_GROUPS = {"names": NAMES_GROUP, "nodes": NODES_GROUP,
              "hierarchies": HIERARCHIES_GROUP, "entrances": ENTRANCES_GROUP,
              "gateways": DIRECTORY_GROUP}
KEPT = ("names", "nodes", "hierarchies", "entrances", "gateways", "releases")
_LIST_KIND = {"nodes": "nodes", "root": "hierarchies", "entrances": "entrances"}
_LIST_ROLE = {"nodes": "the list of nodes", "root": "the hierarchies (root list)",
              "entrances": "the list of web entrances", "scribes": "the list of scribes",
              "sources": "where releases are fetched (sources list)"}
_OWN_ROLE = {"claims": "claims", "reports": "measurements (reports)",
             "proposals": "proposals", "talk": "talk", "log": "log", "room": "room (closed)"}


def moved_to(arts: list[Article], group: str) -> str | None:
    """Where ``group`` moved (UN-RFC 0054 section 14): ``moved_to`` in the newest
    manifest of it that the project key signed, or None."""
    newest = None
    for art in arts:
        if art.group != group or art.control != ["manifest"]:
            continue
        try:
            m = Manifest.from_article(art, stored=True)
        except ArticleError:
            continue
        if crypto.key_to_text(m.owner) != PROJECT_KEY:
            continue
        if newest is None or m.supersedes(newest):
            newest = m
    moved = newest.raw.get(MOVED_TO) if newest is not None else None
    return moved if isinstance(moved, str) and moved != group else None


def registrar_moved_to(arts: list[Article]) -> str | None:
    """The council the project's registrar moved to, or None."""
    return moved_to(arts, REGISTRAR)


def _parts(data: dict) -> list[tuple[str, str, str]]:
    """(group, role, kind) of the groups a council names in its manifest; ``kind`` is
    what that group keeps for the network (``nodes``, ``hierarchies``, ...) or ''."""
    out = []
    lists = data.get("lists") if isinstance(data.get("lists"), dict) else {}
    for kind, g in sorted(lists.items()):
        if isinstance(g, str):
            out.append((g, _LIST_ROLE.get(kind, f"the {kind} list"), _LIST_KIND.get(kind, "")))
    announce = data.get("announce") if isinstance(data.get("announce"), dict) else {}
    for kind, g in sorted(announce.items()):
        if isinstance(g, str):
            if kind == "gateways":
                out.append((g, "the gateway directory", "gateways"))
            else:
                out.append((g, f"where {kind} announce themselves", ""))
    for k, role in _OWN_ROLE.items():
        g = data.get(k)
        if isinstance(g, str):
            if k == "claims":
                role = "hierarchy claims" if lists else "name claims"
            out.append((g, role, ""))
    seen, uniq = set(), []
    for p in out:
        if p[0] not in seen:
            seen.add(p[0])
            uniq.append(p)
    return uniq


def _members(m) -> list:
    return [x.as_json() for x in m.members]


def councils(arts: list[Article], now: datetime) -> dict:
    """The councils that count, counted here from the members' own copies of their
    manifests (UN-RFC 0054 section 5) - never on a node's word - each with the groups
    it keeps; the council groups not (yet) part of any council; and who keeps each of
    the network's shared things: a council, or still the project key."""
    from unseenet.core import council as cn
    copies: dict[str, list[tuple[bytes, str]]] = {}
    for art in arts:
        if not cn.is_council_manifest(art):
            continue
        try:
            author = crypto.key_from_text(art.get("Author-Key", ""))
        except (ValueError, TypeError):
            continue
        copies.setdefault(art.group, []).append((author, art.body))
    chains = {}
    for gid in sorted(copies):
        chain = cn.count_chain(gid, copies[gid])
        if chain.current is not None:
            chains[gid] = chain
    heads = {g for g, c in chains.items()
             if "claims" in c.current.data or "lists" in c.current.data}
    parts_of = {g: _parts(chains[g].current.data) for g in heads}
    named = {p for ps in parts_of.values() for p, _, _ in ps}
    moved = {k: moved_to(arts, REGISTRAR if k == "names" else g) for k, g in OLD_GROUPS.items()}

    def keeper(kind: str) -> str | None:
        to = moved.get(kind)
        if to is None:
            return None
        for g in heads:
            if to == g or to in {p for p, _, _ in parts_of[g]}:
                return g
        return None

    keepers = {k: keeper(k) or "the project key" for k in KEPT}
    out = []
    for gid in sorted(heads):
        chain = chains[gid]
        m = chain.current
        f = m.founding
        parts = []
        takes_on = []
        for g, role, kind in parts_of[gid]:
            pc = chains.get(g)
            if kind:
                takes_on.append(kind)
            parts.append({
                "group": g, "role": role, "kind": kind,
                "counts": pc is not None,
                "in_step": pc is not None and not pc.disputed
                and _members(pc.current) == _members(m),
                "moved": bool(kind) and keepers.get(kind) == gid,
            })
        out.append({
            "group": gid, "name": m.name,
            "keeps": [k for k in KEPT if keepers[k] == gid],
            "takes_on": [k for k in takes_on if keepers.get(k) != gid],
            "since": chain.counted[0].date.date().isoformat(),
            "manifest": m.seq, "members": len(m.keys), "full": len(m.full),
            "on_probation": len(m.on_probation), "quorum": cn.quorum(len(m.full)),
            "min_level": m.min_level, "disputed": chain.disputed,
            "founding_until": f.until.date().isoformat()
            if f is not None and m.founding_lasts(now) else None,
            "parts": parts,
        })
    waiting = []
    for gid in sorted(chains):
        if gid in heads or gid in named:
            continue
        name, _ = split_group_id(gid)
        if name.endswith(COUNCIL_PARTS):
            continue
        m = chains[gid].current
        waiting.append({
            "group": gid, "name": m.name, "members": len(m.keys), "full": len(m.full),
            "since": chains[gid].counted[0].date.date().isoformat(),
            "same_as": [g for g in sorted(heads) if _members(chains[g].current) == _members(m)],
        })
    return {"list": out, "waiting": waiting, "keepers": keepers}
