"""What kind of message an article is, from its headers and its group's manifest.

Only headers every node shows to every reader are used. Nothing here opens an
encrypted article: in closed groups and inboxes the kind (UN-RFC 0028) is inside
the ciphertext, so those articles are counted as "closed" or "private" only.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from unseenet.core import crypto
from unseenet.core.groups import KEY_BOUND_NAMES, PERSONAL_GROUPS

# The categories, in the order the page shows them.
POST, CHAT, COMMENT, FEED, PAGE, REACTION, EDIT, CLOSED, PRIVATE, IMPORTED, SYSTEM = (
    "post", "chat", "comment", "feed", "page", "reaction", "edit", "closed", "private",
    "imported", "system")
CATEGORIES = (POST, CHAT, COMMENT, FEED, PAGE, REACTION, EDIT, CLOSED, PRIVATE, IMPORTED, SYSTEM)

# Categories written by people in Unseenet, in the open: their authors are the
# keys counted as active. Closed and private articles are left out on purpose,
# and so are gateways (their key is the gateway's) and housekeeping. A reaction
# alone does not make a key active: it is one emoji, not something written.
PEOPLE = frozenset({POST, CHAT, COMMENT, FEED, PAGE, EDIT})

# Key-bound groups (UN-RFC 0029): profile@, avatar@, names@, inbox@ and those
# later documents add - the same list the crawler and the nodes use.
KEY_BOUND = KEY_BOUND_NAMES
# Key-bound groups people write in: their own feed and site (UN-RFC 0029 2.1).
# Their articles are counted by view like any other group's; the rest are data.
PERSONAL = frozenset(PERSONAL_GROUPS)          # {"feed", "site"}

# What "system" is made of, for the page's breakdown (never per day).
SYSTEM_PARTS = ("ripening", "profiles", "state", "reports", "control", "lists")
_PART = {"ripe": "ripening", "profile": "profiles", "avatar": "profiles", "names": "profiles",
         "state": "state", "reports": "reports", "labels": "reports"}


@lru_cache(maxsize=65536)
def _fingerprint(key_text: str) -> str:
    try:
        return crypto.fingerprint(crypto.key_from_text(key_text))
    except Exception:  # noqa: BLE001 - a malformed key is simply nobody's
        return ""


@dataclass
class GroupInfo:
    """What the crawler knows about a group from its newest manifest."""
    group_id: str
    type: str = "open"                 # open, moderated, channel, closed, inbox
    view: str = "threads"              # threads, chat, feed, pages, data (UN-RFC 0008, 0034, 0035)
    starters: frozenset = frozenset()  # keys that may start threads in a channel (UN-RFC 0030)
    known: bool = False                # a valid manifest was found

    def __post_init__(self):
        # A personal feed or site is a channel its owner writes in, with the view its
        # name gives (UN-RFC 0029 2.1); its manifest is not fetched, so set it here.
        if not self.known and self.personal:
            self.type, self.view = "channel", PERSONAL_GROUPS[self.name]

    @property
    def name(self) -> str:
        return self.group_id.rpartition("@")[0] or self.group_id

    @property
    def fp(self) -> str:
        return self.group_id.rpartition("@")[2]

    @property
    def key_bound(self) -> str | None:
        return self.name if self.name in KEY_BOUND else None

    @property
    def personal(self) -> bool:
        return self.name in PERSONAL

    @property
    def data_like(self) -> bool:
        """A group for programs, not people: data view, or a key-bound group that
        is not someone's feed or site."""
        return self.view == "data" or (self.key_bound is not None and not self.personal)

    @property
    def hierarchy(self) -> str:
        return self.name.split(".", 1)[0]

    def may_start(self, author: str) -> bool:
        if self.personal:
            return bool(author) and _fingerprint(author) == self.fp
        return author in self.starters


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
    if group.data_like:
        return SYSTEM
    kind = h.get("message-kind", "").strip().lower()
    if kind == "reaction":
        return REACTION                      # UN-RFC 0048
    if h.get("supersedes", "").strip():
        return EDIT                          # UN-RFC 0042: a new version of an earlier article
    author = h.get("author-key", "")
    if group.type == "channel" and h.get("references") and (group.known or group.personal) \
            and not group.may_start(author):
        return COMMENT                       # UN-RFC 0030: replies by non-starters
    if group.view == "feed":
        return FEED                          # UN-RFC 0034
    if group.view == "pages":
        return PAGE                          # UN-RFC 0035
    return CHAT if kind == "chat" else POST


def system_part(h: dict[str, str], group: GroupInfo) -> str:
    """What one system article is, for the breakdown of SYSTEM_PARTS."""
    if group.key_bound in ("reports", "labels") and h.get("control"):
        return "control"                     # an issuer's manifest is not a report
    if group.key_bound in _PART:
        return _PART[group.key_bound]
    if h.get("control"):
        return "control"
    return "lists"                           # node, hierarchy, name lists, canaries
