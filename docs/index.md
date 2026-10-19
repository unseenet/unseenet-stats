---
title: Network statistics
hide:
  - navigation
  - toc
---

<div class="un-hero" markdown>

<div class="un-hero__head">
  <img class="un-hero__icon" src="img/icon.svg" alt="" width="64" height="64">
  <dl class="un-headers" aria-label="Article headers">
    <dt>From</dt><dd>the Unseenet statistics crawler</dd>
    <dt>Newsgroups</dt><dd>unseenet</dd>
    <dt>Date</dt><dd id="st-date">-</dd>
  </dl>
</div>

<h1 class="un-subject"><span class="un-subject__key">Subject:</span> The network, counted.</h1>

<p class="un-lede">
Once a day a crawler connects to the listed nodes over Tor, as an ordinary
reader, and counts what is there: nodes, groups, posts and chats, and the keys
that wrote them. It counts <em>how many</em>, never <em>who</em>. Readers
cannot be counted at all - that is the point of Unseenet.
</p>

<div class="un-actions">
  <a class="un-button un-button--primary" href="https://unseenet.org/">What is Unseenet?</a>
  <a class="un-button" href="#what-is-counted">What is counted, and what is not</a>
</div>

<p class="un-status" id="st-status"><strong>Pre-alpha.</strong> Test nodes may be reset, and
much of the traffic is the project testing itself.</p>

</div>

<script id="st-data" type="application/json"></script>

<noscript><p>This page draws its numbers with JavaScript from
<a href="data/stats.json">data/stats.json</a>, which you can also read directly.</p></noscript>

<div class="st-cards" id="st-cards" aria-live="polite"></div>

## Messages per day { #per-day }

<div class="st-panel">
  <div class="st-panel__bar">
    <p class="st-panel__note">Everything the nodes carried, by the day in its <code>Date</code>
    header. Hover or tap a bar for the day's numbers.</p>
    <div class="st-range" role="group" aria-label="Period">
      <button type="button" data-days="30" aria-pressed="true">30 days</button>
      <button type="button" data-days="90" aria-pressed="false">90 days</button>
      <button type="button" data-days="0" aria-pressed="false">All</button>
    </div>
  </div>
  <div id="st-daily" class="st-chart"></div>
  <ul id="st-legend" class="st-legend"></ul>
</div>

## By kind { #by-kind }

<div class="st-two">
<div class="st-panel">
  <h3 class="st-h">On the nodes now</h3>
  <div id="st-kinds"></div>
</div>
<dl class="st-kinds-help" id="st-kinds-help"></dl>
</div>

## Keys { #keys }

<div class="st-panel">
  <p class="st-panel__note">A key is what you are in Unseenet. One person can have several,
  so this is the number of <strong>keys that wrote something in the open</strong> - posts,
  chats, comments and feed entries - not the number of people.</p>
  <div class="st-minis" id="st-keys"></div>
  <h3 class="st-h">Keys that wrote something, per day</h3>
  <div id="st-keys-daily" class="st-chart st-chart--small"></div>
</div>

## Groups { #groups }

<div class="st-three">
  <div class="st-panel"><h3 class="st-h">By hierarchy</h3><div id="st-hier"></div></div>
  <div class="st-panel"><h3 class="st-h">By type</h3><div id="st-types"></div></div>
  <div class="st-panel"><h3 class="st-h">By view</h3><div id="st-views"></div></div>
</div>

## Gateways and bridges { #gateways }

<div class="st-panel">
  <p class="st-panel__note">Messages brought in from other networks by
  <a href="https://unseenet.org/gateways/">gateways</a> (UN-RFC 0023). They are
  counted apart from Unseenet's own traffic, so one busy gateway does not look like
  a busy network. A gateway signs with its own key, so the people behind the imported
  messages are not counted as keys.</p>
  <div id="st-gateways"></div>
</div>

## Nodes { #nodes }

<div class="st-panel">
  <div class="st-minis" id="st-nodes"></div>
  <p class="st-panel__note">Only the total is shown. A history of when each node was
  reachable would help anyone trying to find where an onion service runs, by matching
  its ups and downs with power cuts or network outages.</p>
</div>

## What is counted, and what is not { #what-is-counted }

<div class="st-rules" markdown>

**Counted.** What any reader of the network can see in the headers every node
shows: how many articles there are, their `Date`, their kind (`Message-Kind`,
UN-RFC 0028), whether they are encrypted, whether a gateway brought them in, and
how many different `Author-Key`s wrote in the open. Group settings come from the
groups' signed manifests.

**Not counted.** Readers - a node cannot tell readers apart, and does not
record what anyone reads. Who wrote what - the page shows numbers only, and the
crawler keeps no list of keys or articles between runs. The kind of a message in a
closed group or a private message, which is encrypted; those are counted only as
"closed" and "private". Nodes that are not on the known-node list.

**How a day's number is kept.** Nodes keep articles for a limited time (90 days
by default). Each crawl counts again every day it can still see, and a day's
number never goes down, so it does not shrink as old articles expire. The only
memory the crawler has is the published file, [`data/stats.json`](data/stats.json).

The crawler and this page are open source:
[unseenet/unseenet-stats](https://github.com/unseenet/unseenet-stats).

</div>
