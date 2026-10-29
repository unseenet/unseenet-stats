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
