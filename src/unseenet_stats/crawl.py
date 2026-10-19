"""Read the network the way any newsreader can, and count what is there.

The crawler connects to each listed node over Tor as an ordinary reader. It
asks for the list of groups, the node's public information (UN-RFC 0011) and,
per group, a few headers of every article with HDR. It never posts, never
decrypts anything and keeps nothing between runs except the published counts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from unseenet.core import crypto
from unseenet.core.article import Article, ArticleError, parse_date
from unseenet.core.groups import Manifest
from unseenet.known_nodes import NODES_GROUP, PROJECT_KEY, builtin_list, parse_node_list
from unseenet.names import NAMES_GROUP
from unseenet.nntp import Client, read_block, strip_reader_headers

from .aggregate import Crawl, Seen, build
from .classify import GroupInfo, category

log = logging.getLogger("unseenet-stats")

# The headers asked for with HDR, for every article of every group.
FIELDS = ("Message-ID", "Date", "Author-Key", "Message-Kind", "Control", "Encrypted",
          "Origin-Network", "References")
MULTILINE = {100, 101, 215, 220, 221, 222, 224, 225, 230, 231}
CHUNK = 20                       # groups per pipelined batch
NODE_TIMEOUT = 900
ATTEMPTS = 4


async def pipeline(c: Client, commands: list[str]) -> list[tuple[int, list[str] | bytes | None]]:
    """Send commands at once and read the answers in order (RFC 3977 section 3.5)."""
    c.writer.write("".join(cmd + "\r\n" for cmd in commands).encode())
    await c.writer.drain()
    out = []
    for cmd in commands:
        code, _ = await c._response()
        body = None
        if code in MULTILINE:
            raw = await read_block(c.reader, limit=200_000_000)
            body = raw if cmd.upper().startswith("ARTICLE") else \
                raw.decode("utf-8", "replace").splitlines()
        out.append((code, body))
    return out


class NodeReading:
    def __init__(self, address: str):
        self.address = address
        self.version = ""
        self.headers: dict[str, dict[str, str]] = {}      # Message-ID -> headers
        self.groups: dict[str, list[str]] = {}            # group -> Message-IDs
        self.subjects: dict[str, list[str]] = {}          # names group only


async def read_node(address: str, socks_port: int | None) -> NodeReading:
    r = NodeReading(address)
    c = await Client.connect(address, socks_port)
    try:
        [(code, info)] = await pipeline(c, ["LIST UNSEENET-NODEINFO"])
        if code == 215 and info:
            try:
                r.version = str(json.loads(info[0]).get("software", ""))[:40]
            except (ValueError, AttributeError):
                pass
        active = []
        for line in await c.list_active():
            parts = line.split()
            if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit() \
                    and int(parts[1]) >= int(parts[2]):
                active.append(parts[0])
        for i in range(0, len(active), CHUNK):
            batch = active[i:i + CHUNK]
            commands = []
            for g in batch:
                commands.append(f"GROUP {g}")
                commands += [f"HDR {f} 1-" for f in FIELDS]
                if g == NAMES_GROUP:
                    commands.append("HDR Subject 1-")
            answers = iter(await pipeline(c, commands))
            for g in batch:
                code, _ = next(answers)
                per_field = {}
                for f in FIELDS + (("Subject",) if g == NAMES_GROUP else ()):
                    fcode, lines = next(answers)
                    if code == 211 and fcode == 225:
                        per_field[f.lower()] = dict(
                            (ln.partition(" ")[0], ln.partition(" ")[2]) for ln in lines or [])
                if code != 211:                  # 411: answers below are not this group's
                    continue
                ids = per_field.get("message-id", {})
                r.groups[g] = []
                for num, msgid in ids.items():
                    if not msgid.startswith("<"):
                        continue
                    h = {f: per_field.get(f, {}).get(num, "") for f in per_field}
                    h["newsgroups"] = g
                    r.headers.setdefault(msgid, h)
                    r.groups[g].append(msgid)
                if g == NAMES_GROUP:
                    r.subjects[g] = list(per_field.get("subject", {}).values())
    finally:
        try:
            await c.quit()
        except Exception:  # noqa: BLE001
            pass
    return r


async def fetch_articles(address: str, socks_port: int | None, ids: list[str]) -> list[Article]:
    """Whole articles by Message-ID (manifests and the node list only)."""
    if not ids:
        return []
    c = await Client.connect(address, socks_port)
    out = []
    try:
        for i in range(0, len(ids), 50):
            for code, raw in await pipeline(c, [f"ARTICLE {m}" for m in ids[i:i + 50]]):
                if code == 220 and raw:
                    try:
                        art = Article.from_bytes(strip_reader_headers(raw))
                        art.verify_signature()
                        out.append(art)
                    except ArticleError:
                        pass
    finally:
        try:
            await c.quit()
        except Exception:  # noqa: BLE001
            pass
    return out


def _date(value: str):
    try:
        return parse_date(value)
    except (TypeError, ValueError):
        return None


def newest_node_list(arts: list[Article]) -> tuple[str, list[str]] | None:
    """(updated, node addresses) from the newest valid list in unseenet.nodes, posted
    by the project key or a poster in the group's signed manifest."""
    info = group_info(NODES_GROUP, [a for a in arts if a.group == NODES_GROUP
                                    and a.control and a.control[0] == "manifest"])
    allowed = info.starters | {PROJECT_KEY}
    best = None
    for art in arts:
        if art.group != NODES_GROUP or art.control or art.get("Author-Key") not in allowed:
            continue
        try:
            updated, nodes = parse_node_list(art.body)
        except ValueError:
            continue
        d = _date(art.get("Date", ""))
        if d and (best is None or d > best[0]):
            best = (d, updated, [n.address for n in nodes])
    return (best[1], best[2]) if best else None


def group_info(group_id: str, manifests: list[Article]) -> GroupInfo:
    newest = None
    for art in manifests:
        try:
            m = Manifest.from_article(art, stored=True)
        except ArticleError:
            continue
        if newest is None or m.supersedes(newest):
            newest = m
    if newest is None:
        return GroupInfo(group_id)
    starters = {newest.owner, *newest.moderators, *newest.posters}
    return GroupInfo(group_id, type=newest.type, view=newest.view,
                     starters=frozenset(crypto.key_to_text(k) for k in starters), known=True)


async def crawl(addresses: list[str] | None, socks_port: int | None) -> Crawl:
    started = datetime.now(timezone.utc)
    if not addresses:
        addresses = [n.address for n in builtin_list()[1]]
    result = Crawl(started=started, nodes_listed=len(addresses))

    async def one(addr):
        # Right after Tor starts, onion services often time out once or twice.
        for attempt in range(ATTEMPTS):
            try:
                return await asyncio.wait_for(read_node(addr, socks_port), NODE_TIMEOUT)
            except Exception as exc:  # noqa: BLE001
                log.warning("could not read %s (try %d): %s", addr[:16], attempt + 1, exc)
                if attempt + 1 < ATTEMPTS:
                    await asyncio.sleep(30)
        return None

    where: dict[str, str] = {}
    fetched: list[Article] = []

    async def fetch_for(rs: list[NodeReading]) -> None:
        """Manifests and node lists: each from the first node that has it."""
        wanted: dict[str, list[str]] = {}
        for r in rs:
            for msgid, h in r.headers.items():
                is_manifest = h.get("control", "").split()[:1] == ["manifest"]
                if (is_manifest or h["newsgroups"] == NODES_GROUP) and msgid not in where:
                    where[msgid] = r.address
                    wanted.setdefault(r.address, []).append(msgid)
        for addr, ids in wanted.items():
            try:
                fetched.extend(await asyncio.wait_for(fetch_articles(addr, socks_port, ids),
                                                      NODE_TIMEOUT))
            except Exception as exc:  # noqa: BLE001
                log.warning("could not fetch manifests from %s: %s", addr[:16], exc)

    readings = [r for r in await asyncio.gather(*(one(a) for a in addresses)) if r]
    await fetch_for(readings)

    # The network's own list (UN-RFC 0010) may name nodes the built-in list does not.
    listed = newest_node_list(fetched)
    if listed:
        result.list_updated = listed[0]
        extra = [a for a in listed[1] if a not in addresses]
        more = [r for r in await asyncio.gather(*(one(a) for a in extra)) if r]
        await fetch_for(more)
        readings += more
        result.nodes_listed = len(set(addresses) | set(listed[1]))
    result.nodes_reached = len(readings)
    for r in readings:
        if r.version:
            result.node_versions[r.version] += 1

    by_group: dict[str, list[Article]] = {}
    for art in fetched:
        if art.control and art.control[0] == "manifest":
            by_group.setdefault(art.group, []).append(art)
    all_groups = {g for r in readings for g in r.groups}
    result.groups = {g: group_info(g, by_group.get(g, [])) for g in sorted(all_groups)}

    for r in readings:
        for msgid, h in r.headers.items():
            if msgid in result.articles:
                continue
            d = _date(h.get("date", ""))
            g = result.groups.get(h["newsgroups"]) or GroupInfo(h["newsgroups"])
            if d is None:
                continue
            cat = category(h, g)
            result.articles[msgid] = Seen(d.astimezone(timezone.utc).date(), g.group_id, cat,
                                          author=h.get("author-key", ""),
                                          network=h.get("origin-network", "").lower()[:32])
        for subject in r.subjects.get(NAMES_GROUP, []):
            if subject.startswith("name "):
                result.names.add(subject[5:].strip().lower())
    return result


async def run(args) -> dict:
    tor = None
    socks = args.socks_port
    if not socks:
        from unseenet.core.tor import TorProcess
        tor = TorProcess(Path(tempfile.mkdtemp(prefix="unseenet-stats-tor-")),
                         TorProcess.find_binary())
        log.info("starting Tor")
        await tor.start(timeout=240)
        socks = tor.socks_port
    try:
        result = await crawl(args.node or None, socks)
    finally:
        if tor:
            await tor.stop()
    out = Path(args.out)
    previous = json.loads(out.read_text()) if out.exists() else None
    stats = build(result, previous)
    if result.nodes_reached == 0:
        raise SystemExit("no node could be reached; the published numbers are left as they were")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stats, indent=1, ensure_ascii=False) + "\n")
    return stats


def main() -> None:
    p = argparse.ArgumentParser(description="Count the Unseenet network from public headers")
    p.add_argument("--out", default="docs/data/stats.json", help="the stats file to update")
    p.add_argument("--socks-port", type=int, help="use a Tor that is already running")
    p.add_argument("--node", action="append", help="a node address (default: the known nodes)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(message)s", stream=sys.stderr)
    stats = asyncio.run(run(args))
    k, n = stats["keys"], stats["nodes"]
    print(f"nodes {n['reached']}/{n['listed']} · groups {stats['groups']['total']} · "
          f"articles {sum(stats['articles']['on_nodes'].values())} · "
          f"active keys 30d {k['active_30']}")


if __name__ == "__main__":
    main()
