<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/unseenet/unseenet/main/assets/logo-dark.svg">
    <img src="https://raw.githubusercontent.com/unseenet/unseenet/main/assets/logo-light.svg" alt="Unseenet" width="360">
  </picture>
</p>

<h1 align="center">unseenet-stats</h1>

<p align="center"><b>Statistics for the Unseenet network.</b><br>
Nodes, groups, posts, chats and active keys, counted once a day from what any reader can see.</p>

<p align="center">
  <a href="https://github.com/unseenet/unseenet-stats/releases"><img src="https://img.shields.io/github/v/release/unseenet/unseenet-stats?include_prereleases&label=release" alt="Release"></a>
  <a href="https://github.com/unseenet/unseenet-stats/actions/workflows/stats.yml"><img src="https://github.com/unseenet/unseenet-stats/actions/workflows/stats.yml/badge.svg" alt="stats"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="Apache-2.0"></a>
</p>

> **Pre-alpha.** Nothing is stable yet, and Unseenet has not had a security
> review. Do not rely on it to protect anyone yet.

## What it is

Statistics for the [Unseenet](https://unseenet.org) network: how many nodes,
groups, posts, chats and active keys there are, counted once a day from what
any reader of the network can see.

**The page:** https://stats.unseenet.org/
**The numbers:** [`docs/data/stats.json`](docs/data/stats.json)

### What it does not count, and why

- **Readers.** Over Tor a node cannot tell readers apart, and nodes do not record
  what anyone reads (UN-RFC 0011). That is the point of Unseenet.
- **Who wrote what.** Only numbers are published. Active keys are counted from
  posts, chats, comments and feed entries in the open - not from closed groups,
  private messages or gateways.
- **Each node's uptime.** Only how many nodes answered. A public history of when
  one onion service was up would help anyone trying to locate it.

The crawler keeps no state between runs except the published file. Nodes keep
articles for a while (90 days by default), so each run counts the recent days
again; a day's numbers never go down, so they do not shrink as articles expire.

## Run it

```sh
pip install .
unseenet-stats -v --out docs/data/stats.json         # starts its own Tor
unseenet-stats --socks-port 9050 --node <address>    # or use a running Tor and one node
pip install mkdocs-material && mkdocs serve           # the page, at http://127.0.0.1:8000
```

The page uses the same theme, logo and styles as unseenet.org.
`docs/stylesheets/brand.css` is a copy of unseenet's `docs/stylesheets/home.css`;
copy it again when the front page's look changes.

## How it works

A GitHub Actions job ([`stats.yml`](.github/workflows/stats.yml)) starts Tor and
connects to every node on the known-node list (UN-RFC 0010) as an ordinary
reader. For each group it asks for a few headers of every article with `HDR`,
and it reads the groups' signed manifests. Key-bound groups - inboxes,
profiles, pictures - are not listed by nodes (UN-RFC 0040), so it finds their
articles with `NEWNEWS` instead and reads their headers with `HEAD`; it counts
them by name and does not fetch their manifests. It never posts and never decrypts
anything. It is built on the Unseenet core, like
[unseenet-bots](https://github.com/unseenet/unseenet-bots), and is also an
example of a program that reads the network.

Each article is counted once (by `Message-ID`, across nodes) as one of:

| Kind | From |
|---|---|
| post, chat | `Message-Kind` (UN-RFC 0028); no header means post |
| comment | a reply in a channel by a key that may not start threads there (UN-RFC 0030) |
| feed | an entry in a group with `"view": "feed"` (UN-RFC 0034, milestone 0.5.0) |
| closed | encrypted, in a closed group: the kind is inside the ciphertext |
| private | an inbox message, sealed for its receiver |
| imported | brought in by a gateway: has `Origin-Network` (UN-RFC 0023) |
| system | control articles, data groups, profiles, avatars, names |

When a new kind of message comes, add it in
[`classify.py`](src/unseenet_stats/classify.py) and the page's `KINDS` in
[`stats.js`](docs/javascripts/stats.js).

## Versions and releases

Versions follow [semantic versioning](https://semver.org/) on the same
principles as [unseenet](https://github.com/unseenet/unseenet/blob/main/docs/development.md#versioning):
tags `vX.Y.Z` on `main`, the changes in [CHANGELOG.md](CHANGELOG.md), and a
GitHub release for each tag. This is one of the project's own services, so it
is not on PyPI. Each release names the minor version of unseenet it works with
(`unseenet>=0.5,<0.6`).

To release: move the entries under `## [Unreleased]` in `CHANGELOG.md` to a
new `## [X.Y.Z] - YYYY-MM-DD` section, set `__version__` in
`src/unseenet_stats/__init__.py`, commit, then
`git tag -a vX.Y.Z -m "unseenet-stats X.Y.Z" && git push origin vX.Y.Z`.

## Part of Unseenet

| Repository | What it is |
|---|---|
| [unseenet](https://github.com/unseenet/unseenet) | The protocol (UN-RFCs), the core library, the node and the command-line client |
| [unseenet-tui](https://github.com/unseenet/unseenet-tui) | The terminal client |
| [unseenet-gui](https://github.com/unseenet/unseenet-gui) | The graphical client - in a window, booted, or in a browser |
| [unseenet-portable](https://github.com/unseenet/unseenet-portable) | Builds the portable clients, Terminal and Graphical, with Tor inside |
| [unseenet-bootable](https://github.com/unseenet/unseenet-bootable) | Builds the bootable images, Terminal and Graphical |
| [unseenet-docs](https://github.com/unseenet/unseenet-docs) | The site [unseenet.org](https://unseenet.org) |
| [unseenet-entrance](https://github.com/unseenet/unseenet-entrance) | Web entrances: the graphical client in an ordinary browser |
| [unseenet-gateway](https://github.com/unseenet/unseenet-gateway) | Gateways to other networks: Usenet, Nostr, Matrix |
| [unseenet-bots](https://github.com/unseenet/unseenet-bots) | Bots that keep channels filled with current content |
| [unseenet-helpbot](https://github.com/unseenet/unseenet-helpbot) | The bot that answers questions in `unseenet.help` |
| [unseenet-watchman](https://github.com/unseenet/unseenet-watchman) | Automatic spam reports and content labels that readers may choose to follow |
| [unseenet-stats](https://github.com/unseenet/unseenet-stats) | Statistics for the network |
| [unseenet-mcp](https://github.com/unseenet/unseenet-mcp) | An MCP server, so a language model can read and post as you (planning) |
| [unseenet-demo](https://github.com/unseenet/unseenet-demo) | Demo people, feeds and sites, made with the command-line client |

## License

[Apache License 2.0](LICENSE). The Unseenet logo: CC BY 4.0.
