"""What kind of message an article is, from its headers and its group's manifest.

Only headers every node shows to every reader are used. Nothing here opens an
encrypted article: in closed groups and inboxes the kind (UN-RFC 0028) is inside
the ciphertext, so those articles are counted as "closed" or "private" only.
"""

from __future__ import annotations

from dataclasses import dataclass

from unseenet.core.groups import KEY_BOUND_NAMES

# The categories, in the order the page shows them.
POST, CHAT, COMMENT, FEED, CLOSED, PRIVATE, IMPORTED, SYSTEM = (
    "post", "chat", "comment", "feed", "closed", "private", "imported", "system")
CATEGORIES = (POST, CHAT, COMMENT, FEED, CLOSED, PRIVATE, IMPORTED, SYSTEM)

# Categories written by people in Unseenet, in the open: their authors are the
# keys counted as active. Closed and private articles are left out on purpose,
# and so are gateways (their key is the gateway's) and housekeeping.
PEOPLE = frozenset({POST, CHAT, COMMENT, FEED})

# Key-bound groups (UN-RFC 0029): profile@, avatar@, names@, inbox@ and those
# later documents add - the same list the crawler and the nodes use.
KEY_BOUND = KEY_BOUND_NAMES


@dataclass
class GroupInfo:
    """What the crawler knows about a group from its newest manifest."""
    group_id: str
    type: str = "open"                 # open, moderated, channel, closed, inbox
    view: str = "threads"              # threads, chat, feed, data (UN-RFC 0008, 0034)
    starters: frozenset = frozenset()  # keys that may start threads in a channel (UN-RFC 0030)
    known: bool = False                # a valid manifest was found

    @property
    def name(self) -> str:
        return self.group_id.rpartition("@")[0] or self.group_id

    @property
    def key_bound(self) -> str | None:
        return self.name if self.name in KEY_BOUND else None

    @property
    def hierarchy(self) -> str:
        return self.name.split(".", 1)[0]


def category(h: dict[str, str], group: GroupInfo) -> str:
    """The category of one article. ``h`` holds lower-case header names."""
    if h.get("control"):
        return SYSTEM
    encrypted = h.get("encrypted", "").strip()
    if group.type == "inbox" or group.key_bound == "inbox" or encrypted == "sealedbox":
        return PRIVATE
    if encrypted or group.type == "closed":
        return CLOSED
    if h.get("origin-network"):
        return IMPORTED
    if group.view == "data" or group.key_bound:
        return SYSTEM
    author = h.get("author-key", "")
    if group.type == "channel" and h.get("references") and group.known \
            and author not in group.starters:
        return COMMENT                       # UN-RFC 0030: replies by non-starters
    if group.view == "feed":
        return FEED                          # UN-RFC 0034 (milestone 0.5.0)
    return CHAT if h.get("message-kind", "").strip().lower() == "chat" else POST
