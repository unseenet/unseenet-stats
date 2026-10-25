# Changelog

All notable changes to unseenet-stats are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org/) on the same principles as
[unseenet](https://github.com/unseenet/unseenet/blob/main/docs/development.md#versioning).
The daily counts themselves are data commits, not changes listed here.

## [Unreleased]

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
