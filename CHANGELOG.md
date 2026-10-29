# Changelog

All notable changes to unseenet-stats are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org/) on the same principles as
[unseenet](https://github.com/unseenet/unseenet/blob/main/docs/development.md#versioning).
The daily counts themselves are data commits, not changes listed here.

## [Unreleased]

For unseenet 0.6 (`unseenet>=0.6,<0.7`): release once the nodes run 0.6.

### Fixed

- Entries, comments and pages in people's own feeds and sites (`feed@`, `site@`)
  were counted as housekeeping; they are now counted by their view (#11).
- Reactions, pages and edits were counted as posts. They are now categories of
  their own; a reaction alone does not make a key active (#11).
- Days the nodes still carry are counted again under the new rules, instead of
  being added to the old counts.

### Added

- Housekeeping split into its parts (key ripening, profiles, state, spam reports
  and labels, control, lists), and the number of personal feeds and sites (#11).
- Messages per day leave out gateways unless asked: one gateway backfill brought
  in over 4,000 messages on one day and flattened everything else.

- Released versions, read from the network: the newest stable and development
  release signed in `unseenet.releases`, and how many nodes run the newest stable (#12).
- Nodes by name from the known-node list, the project's own and others', and
  what the answering nodes carry, as totals from their NODEINFO (#13).
- Web entrances from `unseenet.entrances`, with whether the https ones answer,
  and the gateways announced in `unseenet.gateways` (#14).
- The network's lists: hierarchies by policy, names, and whether yesterday's
  canaries reached every node (#15).
- Spam reports and labels with their number of issuers, and active keys without
  bots (their profile says so) and the demo's people (#16).

### Changed

- Workflows use `actions/checkout@v5` and `actions/setup-python@v6`.

## [0.2.0] - 2026-10-25

For unseenet 0.5 (`unseenet>=0.5,<0.6`): the crawler reads 0.5 nodes.

## [0.1.0] - 2026-10-22

The first release. Works with unseenet 0.4 (`unseenet>=0.4.1,<0.5`).

### Added

- A crawler that counts the network from what any reader can see: known
  nodes, groups and posts (gateways included), split by kind, and the keys
  seen posting; key-bound groups are found with NEWNEWS (UN-RFC 0040, #1).
- A daily workflow that counts and publishes the figures as
  [stats.unseenet.org](https://stats.unseenet.org), branded like
  unseenet.org.

[Unreleased]: https://github.com/unseenet/unseenet-stats/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/unseenet/unseenet-stats/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/unseenet/unseenet-stats/releases/tag/v0.1.0
