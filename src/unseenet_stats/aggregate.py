"""Turn what one crawl saw into the published numbers, merged with earlier days.

The crawler keeps no state of its own: no list of keys, no list of articles.
Everything it remembers between runs is in the published ``stats.json``, which
holds only counts. Nodes keep articles for a while (90 days by default), so each
crawl can count the recent days again; a day's count never goes down, so a day
does not shrink when its articles expire from the nodes.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from .classify import CATEGORIES, IMPORTED, PEOPLE, SYSTEM, SYSTEM_PARTS, GroupInfo

# 2: categories page, reaction and edit; personal feeds and sites counted by view
# (#11). Days counted under version 1 that the nodes still carry are counted again.
VERSION = 2


@dataclass
class Seen:
    """One article, as the crawl needs it. Kept in memory during one run only."""
    day: date
    group_id: str
    category: str
    author: str = ""
    network: str = ""
    part: str = ""             # what a system article is (classify.SYSTEM_PARTS)


@dataclass
class Crawl:
    """Everything one run collected."""
    started: datetime
    articles: dict[str, Seen] = field(default_factory=dict)       # by Message-ID
    groups: dict[str, GroupInfo] = field(default_factory=dict)
    nodes_listed: int = 0
    nodes_reached: int = 0
    node_versions: Counter = field(default_factory=Counter)
    list_updated: str = ""
    names: set[str] = field(default_factory=set)                   # registered names


def _days(crawl: Crawl) -> dict[str, dict]:
    cats: dict[str, Counter] = defaultdict(Counter)
    keys: dict[str, set] = defaultdict(set)
    for a in crawl.articles.values():
        d = a.day.isoformat()
        cats[d][a.category] += 1
        if a.category in PEOPLE and a.author:
            keys[d].add(a.author)
    return {d: {"categories": dict(c), "keys": len(keys[d])} for d, c in cats.items()}


def _active(crawl: Crawl, days: int) -> int:
    since = crawl.started.date() - timedelta(days=days - 1)
    return len({a.author for a in crawl.articles.values()
                if a.category in PEOPLE and a.author and a.day >= since})


def merge_days(old: list[dict], new: dict[str, dict], today: date,
               recount: bool = False) -> list[dict]:
    """Earlier days plus this crawl's, never lowering a count. Days in the future
    (a wrong clock in a Date header) are dropped. With ``recount`` (the earlier
    file was counted under other rules), a day this crawl saw is replaced, not merged."""
    by_day = {d["date"]: d for d in old}
    for d, v in new.items():
        if date.fromisoformat(d) > today:
            continue
        if recount:
            by_day.pop(d, None)
        cur = by_day.setdefault(d, {"date": d, "categories": {}, "keys": 0})
        for cat, n in v["categories"].items():
            cur["categories"][cat] = max(cur["categories"].get(cat, 0), n)
        cur["keys"] = max(cur["keys"], v["keys"])
    return [by_day[d] for d in sorted(by_day)]


def build(crawl: Crawl, previous: dict | None = None) -> dict:
    today = crawl.started.date()
    previous = previous or {}
    recount = bool(previous) and previous.get("v") != VERSION
    days = merge_days(previous.get("days", []), _days(crawl), today, recount=recount)

    in_window = Counter()
    for a in crawl.articles.values():
        in_window[a.category] += 1
    total = Counter()
    for d in days:
        total.update(d["categories"])

    groups = [g for g in crawl.groups.values()]
    # Groups for people: not data, not inboxes, and of the key-bound ones only
    # personal feeds and sites - counted apart, as there is one per person.
    people_groups = [g for g in groups
                     if not g.key_bound and g.view != "data" and g.type != "inbox"]
    personal = Counter(g.name for g in groups if g.personal)
    system = Counter(a.part for a in crawl.articles.values() if a.category == SYSTEM)
    hier_articles = Counter(crawl.groups[a.group_id].hierarchy
                            for a in crawl.articles.values()
                            if a.category in PEOPLE and a.group_id in crawl.groups
                            and not crawl.groups[a.group_id].personal)

    networks: dict[str, dict] = {}
    for a in crawl.articles.values():
        if a.category == IMPORTED:
            n = networks.setdefault(a.network, {"articles": 0, "gateways": set(), "groups": set()})
            n["articles"] += 1
            n["gateways"].add(a.author)
            n["groups"].add(a.group_id)

    return {
        "v": VERSION,
        "generated": crawl.started.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "categories": list(CATEGORIES),
        "nodes": {"listed": crawl.nodes_listed, "reached": crawl.nodes_reached,
                  "versions": dict(crawl.node_versions.most_common()),
                  "list_updated": crawl.list_updated},
        "groups": {
            "total": len(people_groups),
            "by_type": dict(Counter(g.type for g in people_groups).most_common()),
            "by_view": dict(Counter(g.view for g in people_groups).most_common()),
            "by_hierarchy": dict(Counter(g.hierarchy for g in people_groups).most_common()),
            "personal": {"feeds": personal.get("feed", 0), "sites": personal.get("site", 0)},
        },
        "articles": {
            "on_nodes": dict(in_window),
            "system_parts": {k: system[k] for k in SYSTEM_PARTS if system[k]},
            "counted_since_start": dict(total),
            "by_hierarchy": dict(hier_articles.most_common()),
        },
        "keys": {
            "active_7": _active(crawl, 7),
            "active_30": _active(crawl, 30),
            "active_90": _active(crawl, 90),
            "profiles": sum(1 for g in groups if g.key_bound == "profile"),
            "inboxes": sum(1 for g in groups if g.key_bound == "inbox" or g.type == "inbox"),
            "names": len(crawl.names),
        },
        "gateways": {
            net: {"articles": v["articles"], "gateways": len(v["gateways"]),
                  "groups": len(v["groups"])}
            for net, v in sorted(networks.items())
        },
        "days": days,
    }
