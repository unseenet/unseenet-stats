"""The crawler finds key-bound groups with NEWNEWS, whether the node lists them or not
(UN-RFC 0040 sections 3 and 5). Runs a node in-process; no Tor."""

import asyncio
from datetime import datetime, timezone

import pytest

from unseenet.core import crypto
from unseenet.core.article import new_article
from unseenet.core.groups import inbox_article, is_key_bound, make_manifest
from unseenet.core.store import Store
from unseenet.node.server import Node, NodeConfig

from unseenet_stats import crawl
from unseenet_stats.aggregate import Crawl, Seen, build
from unseenet_stats.classify import GroupInfo, category

BITS = 8


def _node() -> Node:
    node = Node(Store(), NodeConfig(min_pow=BITS, forward_delay=(0, 0)))
    owner, poster = crypto.Identity.generate(), crypto.Identity.generate()
    snak = make_manifest(owner, "dk.snak", "open", pow_bits=BITS)
    inbox = make_manifest(owner, "inbox", "inbox", pow_bits=BITS)
    profile = make_manifest(owner, "profile", "open", pow_bits=BITS)
    for art in (snak, inbox, profile):
        node.accept(art.to_bytes())
    node.accept(new_article(snak.group, "Hej", "hej\n", from_name="p")
                .finalize(poster, BITS).to_bytes())
    for _ in range(2):
        node.accept(inbox_article(inbox.group, owner.public_key, from_name="p", subject="s",
                                  body="b", sender=poster, pow_bits=BITS).to_bytes())
    return node


def _as_after_0040(node: Node) -> None:
    """Make the node answer as UN-RFC 0040 says: key-bound groups out of LIST and
    out of part 1 of NEWNEWS (both come from Store.groups), part 2 unchanged."""
    groups = node.store.groups
    node.store.groups = lambda *a, **kw: [g for g in groups(*a, **kw) if not is_key_bound(g[0])]


async def _read(node: Node) -> crawl.NodeReading:
    server = await node.serve("127.0.0.1", 0)
    try:
        return await crawl.read_node(f"127.0.0.1:{server.sockets[0].getsockname()[1]}", None)
    finally:
        server.close()


@pytest.mark.parametrize("after_0040", [False, True])
def test_key_bound_groups_counted_with_and_without_listing(after_0040):
    node = _node()
    if after_0040:
        _as_after_0040(node)
    r = asyncio.run(_read(node))

    kinds = sorted(g.split("@")[0] for g in r.groups)
    assert kinds == ["dk.snak", "inbox", "profile"]
    inbox = next(g for g in r.groups if g.startswith("inbox@"))
    assert len(r.groups[inbox]) == 3                     # the manifest and two private posts
    assert all(r.headers[m]["newsgroups"] == inbox for m in r.groups[inbox])

    c = Crawl(started=datetime.now(timezone.utc))
    c.groups = {g: GroupInfo(g) for g in r.groups}
    for msgid, h in r.headers.items():
        d = crawl._date(h["date"])
        c.articles[msgid] = Seen(d.date(), h["newsgroups"], category(h, c.groups[h["newsgroups"]]))
    stats = build(c)
    assert stats["keys"]["profiles"] == 1 and stats["keys"]["inboxes"] == 1
    assert stats["articles"]["on_nodes"]["private"] == 2
    assert stats["groups"]["total"] == 1                  # dk.snak only


def test_parse_head_folds_and_keeps_the_first():
    h = crawl.parse_head(["Newsgroups: inbox@x", "Subject: a", " b", "Subject: c", "junk"])
    assert h == {"newsgroups": "inbox@x", "subject": "a b"}
