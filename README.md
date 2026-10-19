# unseenet-stats

Statistics for the [Unseenet](https://unseenet.org) network: how many nodes,
groups, posts, chats and active keys there are, counted once a day from what
any reader of the network can see.

**The page:** https://stats.unseenet.org/
**The numbers:** [`docs/data/stats.json`](docs/data/stats.json)

## How it counts

A GitHub Actions job ([`stats.yml`](.github/workflows/stats.yml)) starts Tor and
connects to every node on the known-node list (UN-RFC 0010) as an ordinary
reader. For each group it asks for a few headers of every article with `HDR`,
and it reads the groups' signed manifests. It never posts and never decrypts
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

## What it does not count, and why

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

## Running it yourself

```sh
pip install .
unseenet-stats -v --out docs/data/stats.json         # starts its own Tor
unseenet-stats --socks-port 9050 --node <address>    # or use a running Tor and one node
pip install mkdocs-material && mkdocs serve           # the page, at http://127.0.0.1:8000
```

The page uses the same theme, logo and styles as unseenet.org.
`docs/stylesheets/brand.css` is a copy of unseenet's `docs/stylesheets/home.css`;
copy it again when the front page's look changes.

## License

Code Apache-2.0. The Unseenet logo is CC BY 4.0. The numbers are free to use.
