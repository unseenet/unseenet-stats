/* Draws the statistics page from data/stats.json. No libraries, no outside calls. */
(function () {
  "use strict";

  var KINDS = {
    post:     { label: "Posts",          help: "Messages meant to be read on their own, with a subject: threads and replies (UN-RFC 0028)." },
    chat:     { label: "Chats",          help: "Short lines in a running conversation, in chat groups or mixed groups (UN-RFC 0028)." },
    comment:  { label: "Comments",       help: "Replies in a channel by someone who is not one of its writers (UN-RFC 0030)." },
    feed:     { label: "Feed entries",   help: "Entries in feeds people follow - their own feeds and shared ones - newest first (UN-RFC 0034)." },
    page:     { label: "Pages",          help: "Pages of sites, people's own and shared ones (UN-RFC 0035)." },
    reaction: { label: "Reactions",      help: "A single emoji on a post, chat line or comment (UN-RFC 0048). A reaction alone does not make a key count as active." },
    edit:     { label: "Edits",          help: "New versions of something already written, replacing the earlier one (UN-RFC 0042)." },
    closed:   { label: "Closed groups",  help: "Messages in closed groups. They are encrypted, so whether each one is a chat or a post is not visible." },
    private:  { label: "Private",        help: "Private chats and posts between two keys, sealed for the receiver. Only the number is visible." },
    imported: { label: "From gateways",  help: "Messages a gateway brought in from another network, such as Usenet or Nostr (UN-RFC 0023)." },
    system:   { label: "Housekeeping",   help: "What programs read, not people: key ripening, profiles and pictures, each person's encrypted state, spam reports and labels, group settings, and the network's lists and canaries." }
  };
  var VIEWS = { threads: "Discussion", chat: "Chat", feed: "Feed", pages: "Site", data: "Data" };
  var SYSTEM_PARTS = {
    ripening: "Key ripening",
    profiles: "Profiles, pictures",
    state:    "Encrypted state",
    reports:  "Reports, labels",
    control:  "Group settings",
    lists:    "Lists, canaries"
  };
  var TYPES = { open: "Open", moderated: "Moderated", channel: "Channel", closed: "Closed", inbox: "Inbox" };

  var data = null;
  var range = 30;
  var withGateways = false;     // gateways can bring in thousands at once (backfill)

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) { e.setAttribute(k, attrs[k]); }
    if (text !== undefined) { e.textContent = text; }
    return e;
  }
  function svg(tag, attrs) {
    var e = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in attrs || {}) { e.setAttribute(k, attrs[k]); }
    return e;
  }
  function fmt(n) { return (n || 0).toLocaleString("en"); }
  function sum(o) { var s = 0; for (var k in o || {}) { s += o[k]; } return s; }
  function byId(id) { return document.getElementById(id); }

  function card(box, value, label, sub) {
    var c = el("div", { "class": "st-card" });
    c.appendChild(el("span", { "class": "st-card__value" }, value));
    c.appendChild(el("span", { "class": "st-card__label" }, label));
    if (sub) { c.appendChild(el("span", { "class": "st-card__sub" }, sub)); }
    box.appendChild(c);
  }

  /* Horizontal bars, one row per entry, largest first. */
  function bars(box, entries, names, kindClass) {
    box.textContent = "";
    entries = entries.filter(function (e) { return e[1] > 0; });
    if (!entries.length) { box.appendChild(el("p", { "class": "st-empty" }, "Nothing yet.")); return; }
    var max = Math.max.apply(null, entries.map(function (e) { return e[1]; }));
    var list = el("ul", { "class": "st-bars" });
    entries.forEach(function (e) {
      var li = el("li");
      li.appendChild(el("span", { "class": "st-bars__name" }, (names && names[e[0]]) || e[0]));
      var track = el("span", { "class": "st-bars__track" });
      var bar = el("span", { "class": "st-bars__bar" });
      if (kindClass) { bar.style.background = "var(--k-" + e[0] + ")"; }
      bar.style.width = Math.max(2, Math.round(100 * e[1] / max)) + "%";
      track.appendChild(bar);
      li.appendChild(track);
      li.appendChild(el("span", { "class": "st-bars__n" }, fmt(e[1])));
      list.appendChild(li);
    });
    box.appendChild(list);
  }
  function entriesOf(obj, order) {
    var keys = order || Object.keys(obj || {});
    return keys.filter(function (k) { return obj && obj[k] !== undefined; })
      .map(function (k) { return [k, obj[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; });
  }

  /* All days from the first to the last, with empty days filled in. */
  function dayList() {
    var days = data.days || [];
    if (!days.length) { return []; }
    var have = {};
    days.forEach(function (d) { have[d.date] = d; });
    var out = [];
    var end = new Date(data.generated.slice(0, 10) + "T00:00:00Z");
    var start = new Date(days[0].date + "T00:00:00Z");
    if (range) {                       // the whole period, empty days included
      start = new Date(end.getTime() - (range - 1) * 86400000);
    }
    for (var t = start.getTime(); t <= end.getTime(); t += 86400000) {
      var iso = new Date(t).toISOString().slice(0, 10);
      out.push(have[iso] || { date: iso, categories: {}, keys: 0 });
    }
    return out;
  }

  /* A bar per day; stacked by kind, or one value per day. */
  function dayChart(box, days, stacked, height) {
    box.textContent = "";
    if (!days.length) { box.appendChild(el("p", { "class": "st-empty" }, "No data yet.")); return; }
    var W = 760, H = height, padL = 34, padB = 22, padT = 8;
    var cats = data.categories.filter(function (c) {
      return KINDS[c] && (withGateways || c !== "imported");
    });
    var totals = days.map(function (d) {
      return stacked ? cats.reduce(function (t, c) { return t + (d.categories[c] || 0); }, 0) : d.keys;
    });
    var max = Math.max(1, Math.max.apply(null, totals));
    var step = Math.pow(10, Math.floor(Math.log10(max)));
    var top = Math.ceil(max / step) * step;
    var s = svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "class": "st-svg" });
    s.appendChild(svg("title")).textContent = stacked ? "Messages per day, by kind" : "Keys that wrote something, per day";
    var plotH = H - padB - padT, plotW = W - padL - 4;
    [0, top / 2, top].forEach(function (v) {
      var y = padT + plotH - plotH * v / top;
      s.appendChild(svg("line", { x1: padL, x2: W - 4, y1: y, y2: y, "class": "st-grid" }));
      var t = svg("text", { x: padL - 6, y: y + 4, "class": "st-axis", "text-anchor": "end" });
      t.textContent = fmt(Math.round(v));
      s.appendChild(t);
    });
    var bw = plotW / days.length;
    var gap = Math.min(3, bw * 0.2);
    var tip = byId("st-tip");
    days.forEach(function (d, i) {
      var x = padL + i * bw + gap / 2, y = padT + plotH;
      var g = svg("g", { "class": "st-day", tabindex: "0" });
      var parts = stacked ? cats.map(function (c) { return [c, d.categories[c] || 0]; }) : [["keys", d.keys]];
      parts.forEach(function (p) {
        if (!p[1]) { return; }
        var h = plotH * p[1] / top;
        y -= h;
        g.appendChild(svg("rect", { x: x, y: y, width: Math.max(1, bw - gap), height: h,
                                    "class": stacked ? "k-" + p[0] : "k-keys" }));
      });
      g.appendChild(svg("rect", { x: padL + i * bw, y: padT, width: bw, height: plotH, "class": "st-hit" }));
      var lines = [d.date].concat(parts.filter(function (p) { return p[1]; }).map(function (p) {
        return (stacked ? KINDS[p[0]].label : "Keys") + ": " + fmt(p[1]);
      }));
      if (lines.length === 1) { lines.push("Nothing"); }
      function show(ev) {
        tip.textContent = "";
        lines.forEach(function (l, j) { tip.appendChild(el(j ? "span" : "strong", {}, l)); });
        var r = box.getBoundingClientRect(), b = g.getBoundingClientRect();
        tip.style.left = Math.min(r.width - 150, Math.max(0, b.left - r.left + b.width / 2 - 75)) + "px";
        tip.style.top = (b.top - r.top - 8) + "px";
        tip.hidden = false;
        box.appendChild(tip);
      }
      g.addEventListener("mouseenter", show);
      g.addEventListener("focus", show);
      g.addEventListener("click", show);
      g.addEventListener("mouseleave", function () { tip.hidden = true; });
      g.addEventListener("blur", function () { tip.hidden = true; });
      s.appendChild(g);
      var every = Math.ceil(days.length / 8);
      if (i % every === 0) {
        var t = svg("text", { x: padL + i * bw + bw / 2, y: H - 6, "class": "st-axis", "text-anchor": "middle" });
        t.textContent = d.date.slice(5);
        s.appendChild(t);
      }
    });
    box.appendChild(s);
  }

  function drawDays() {
    var days = dayList();
    dayChart(byId("st-daily"), days, true, 240);
    dayChart(byId("st-keys-daily"), days, false, 150);
  }

  function render() {
    var d = data;
    // "Mon, 19 Oct 2026 07:37 UTC", like a Date header
    byId("st-date").textContent = new Date(d.generated).toUTCString().replace(/:\d\d GMT$/, " UTC");
    var people = ["post", "chat", "comment", "feed", "page"].reduce(function (s, k) { return s + (d.articles.on_nodes[k] || 0); }, 0);

    var cards = byId("st-cards");
    cards.textContent = "";
    card(cards, d.nodes.reached + " / " + d.nodes.listed, "nodes answered", "of the listed nodes, today");
    card(cards, fmt(d.groups.total), "groups", "for people, not counting inboxes and lists");
    card(cards, fmt(people), "posts, chats, comments and pages", "on the nodes now, in the open");
    card(cards, fmt(d.keys.active_30), "active keys", "wrote something in the last 30 days");

    var legend = byId("st-legend");
    legend.textContent = "";
    d.categories.filter(function (k) { return KINDS[k]; }).forEach(function (k) {
      var li = el("li");
      li.appendChild(el("span", { "class": "st-swatch k-" + k, "aria-hidden": "true" }));
      li.appendChild(document.createTextNode(KINDS[k].label));
      legend.appendChild(li);
    });
    drawDays();

    bars(byId("st-system"), entriesOf((d.articles.system_parts) || {}), SYSTEM_PARTS);
    bars(byId("st-kinds"), d.categories.filter(function (k) { return KINDS[k]; }).map(function (k) { return [k, d.articles.on_nodes[k] || 0]; }),
         Object.fromEntries(d.categories.filter(function (k) { return KINDS[k]; }).map(function (k) { return [k, KINDS[k].label]; })), true);
    var help = byId("st-kinds-help");
    help.textContent = "";
    d.categories.filter(function (k) { return KINDS[k]; }).forEach(function (k) {
      var dt = el("dt");
      dt.appendChild(el("span", { "class": "st-swatch k-" + k, "aria-hidden": "true" }));
      dt.appendChild(document.createTextNode(KINDS[k].label));
      help.appendChild(dt);
      help.appendChild(el("dd", {}, KINDS[k].help));
    });

    var keys = byId("st-keys");
    keys.textContent = "";
    card(keys, fmt(d.keys.active_7), "active, 7 days");
    card(keys, fmt(d.keys.active_30), "active, 30 days");
    card(keys, fmt(d.keys.active_90), "active, 90 days");
    if (d.keys.people_30 !== undefined) {
      card(keys, fmt(d.keys.people_30), "without bots and demo", "active, 30 days (" + fmt(d.keys.bots) + " bots, " + fmt(d.keys.demo) + " demo people)");
    }
    card(keys, fmt(d.keys.names), "names", "claimed, like @lorensen");
    card(keys, fmt(d.keys.profiles), "profiles");
    card(keys, fmt(d.keys.inboxes), "inboxes", "can receive private messages");

    var personal = d.groups.personal || {};
    var pbox = byId("st-personal");
    pbox.textContent = "";
    card(pbox, fmt(personal.feeds), "personal feeds", "one person's own feed");
    card(pbox, fmt(personal.sites), "personal sites", "one person's own site");
    bars(byId("st-hier"), entriesOf(d.groups.by_hierarchy).map(function (e) { return [e[0] + ".*", e[1]]; }));
    bars(byId("st-types"), entriesOf(d.groups.by_type), TYPES);
    bars(byId("st-views"), entriesOf(d.groups.by_view), VIEWS);

    var gw = byId("st-gateways");
    gw.textContent = "";
    var nets = Object.keys(d.gateways || {});
    if (!nets.length) {
      gw.appendChild(el("p", { "class": "st-empty" }, "No gateways are bringing anything in yet."));
    } else {
      var table = el("table", { "class": "st-table" });
      var head = el("tr");
      ["Network", "Messages on the nodes", "Gateways", "Groups"].forEach(function (h) { head.appendChild(el("th", { scope: "col" }, h)); });
      table.appendChild(el("thead")).appendChild(head);
      var body = el("tbody");
      nets.forEach(function (n) {
        var g = d.gateways[n], tr = el("tr");
        tr.appendChild(el("th", { scope: "row" }, n.charAt(0).toUpperCase() + n.slice(1)));
        [g.articles, g.gateways, g.groups].forEach(function (v) { tr.appendChild(el("td", {}, fmt(v))); });
        body.appendChild(tr);
      });
      table.appendChild(body);
      gw.appendChild(table);
    }

    var nodes = byId("st-nodes");
    nodes.textContent = "";
    var nl = d.node_list || null;
    card(nodes, fmt(d.nodes.listed), "listed nodes", d.nodes.list_updated ? "list of " + d.nodes.list_updated : "");
    if (nl) {
      card(nodes, fmt(nl.others), "run by others", nl.others ? "not by the project" : "none yet - run one?");
      card(nodes, fmt(nl.project), "run by the project");
    }
    card(nodes, fmt(d.nodes.reached), "answered today");
    entriesOf(d.nodes.versions).forEach(function (e) {
      card(nodes, fmt(e[1]), e[0].replace(/^unseenet /, "version "), "nodes running it");
    });

    var names = byId("st-node-names");
    names.textContent = "";
    ((nl && nl.list) || []).forEach(function (n) {
      var li = el("li", { "class": n.project ? "st-names__own" : "" }, n.name);
      if (n.project) { li.appendChild(el("span", { "class": "st-tag" }, "project")); }
      names.appendChild(li);
    });
    var pol = byId("st-policies");
    pol.textContent = "";
    if (nl && nl.policies) {
      var p = nl.policies, r = d.nodes.reached;
      card(pol, p.files + " / " + r, "carry files", "pictures and documents (UN-RFC 0027)");
      card(pol, p.encrypted_files + " / " + r, "carry encrypted files", "for closed groups and private posts");
      card(pol, p.sites + " / " + r, "carry sites");
      card(pol, p.profiles + " / " + r, "carry profiles");
      if (p.retention_days && p.retention_days.length) {
        card(pol, p.retention_days[0] === p.retention_days[1] ? String(p.retention_days[0])
             : p.retention_days[0] + "-" + p.retention_days[1], "days kept", "before articles expire");
      }
    }

    var rel = byId("st-releases");
    rel.textContent = "";
    var rs = d.releases || {};
    if (rs.stable) { card(rel, rs.stable.version, "stable", "signed " + rs.stable.date + " with the " + rs.stable.signed_by); }
    if (rs.dev) { card(rel, rs.dev.version, "development build", rs.dev.date); }
    if (rs.stable && nl) { card(rel, nl.on_stable + " / " + d.nodes.reached, "nodes on " + rs.stable.version, "the newest stable"); }
    if (!rs.stable && !rs.dev) { rel.appendChild(el("p", { "class": "st-empty" }, "No signed releases found.")); }

    var dir = byId("st-gw-dir");
    dir.textContent = "";
    var gws = d.gateway_directory || [];
    if (!gws.length) {
      dir.appendChild(el("p", { "class": "st-empty" }, "No gateway has announced itself yet."));
    } else {
      var t = el("table", { "class": "st-table" });
      var h = el("tr");
      ["Gateway", "Networks", "Groups"].forEach(function (x) { h.appendChild(el("th", { scope: "col" }, x)); });
      t.appendChild(el("thead")).appendChild(h);
      var tb = el("tbody");
      gws.forEach(function (g) {
        var tr = el("tr");
        tr.appendChild(el("th", { scope: "row" }, g.name));
        tr.appendChild(el("td", {}, g.networks.map(function (n) {
          var dirn = n["import"] && n["export"] ? "both ways" : n["import"] ? "in" : "out";
          return n.network.charAt(0).toUpperCase() + n.network.slice(1) + " (" + dirn + ")";
        }).join(", ")));
        tr.appendChild(el("td", {}, fmt(g.groups)));
        tb.appendChild(tr);
      });
      t.appendChild(tb);
      dir.appendChild(t);
    }

    var en = byId("st-entrances");
    en.textContent = "";
    var es = d.entrances || { list: [] };
    if (!es.list.length) {
      en.appendChild(el("p", { "class": "st-empty" }, "No entrances are listed yet."));
    } else {
      var et = el("table", { "class": "st-table" });
      var eh = el("tr");
      ["Entrance", "On the web", "Over Tor", "Answers now"].forEach(function (x) { eh.appendChild(el("th", { scope: "col" }, x)); });
      et.appendChild(el("thead")).appendChild(eh);
      var eb = el("tbody");
      es.list.forEach(function (e) {
        var tr = el("tr");
        tr.appendChild(el("th", { scope: "row" }, e.name));
        var web = el("td");
        if (e.url) { web.appendChild(el("a", { href: e.url, rel: "nofollow noopener" }, e.url.replace(/^https:\/\//, "").replace(/\/$/, ""))); }
        else { web.textContent = "-"; }
        tr.appendChild(web);
        tr.appendChild(el("td", {}, e.onion ? "yes" : "-"));
        tr.appendChild(el("td", {}, e.url ? (e.answers ? "yes" : "no") : "not checked"));
        eb.appendChild(tr);
      });
      et.appendChild(eb);
      en.appendChild(et);
    }

    var lists = byId("st-lists");
    lists.textContent = "";
    var hi = d.hierarchies || {};
    if (hi.total) {
      var bp = hi.by_policy || {};
      card(lists, fmt(hi.total), "hierarchies", (bp.free || 0) + " free, " + (bp.governed || 0) + " governed, " + (bp.reserved || 0) + " reserved");
    }
    card(lists, fmt(d.keys.names), "names", "claimed, like @lorensen");
    var ca = d.canary;
    if (ca) { card(lists, ca.everywhere + " / " + ca.posted, "canaries everywhere", "of " + ca.date + ": reached every node"); }
    var mo = d.moderation;
    if (mo) {
      card(lists, fmt(mo.reports), "spam reports and labels", "on the nodes now");
      card(lists, fmt(mo.report_issuers + mo.label_issuers), "issuers", "that anyone may choose to follow");
    }
  }

  function start() {
    if (!byId("st-cards")) { return; }
    var tip = el("div", { id: "st-tip", "class": "st-tip", role: "status" });
    tip.hidden = true;
    document.body.appendChild(tip);
    document.querySelectorAll(".st-range button").forEach(function (b) {
      b.addEventListener("click", function () {
        range = parseInt(b.getAttribute("data-days"), 10);
        document.querySelectorAll(".st-range button").forEach(function (o) {
          o.setAttribute("aria-pressed", o === b ? "true" : "false");
        });
        if (data) { drawDays(); }
      });
    });
    var gw = byId("st-with-gw");
    if (gw) {
      gw.addEventListener("change", function () { withGateways = gw.checked; if (data) { drawDays(); } });
    }
    var inline = byId("st-data");
    if (inline && inline.textContent.trim()) {
      try { data = JSON.parse(inline.textContent); } catch (e) { data = null; }
      if (data) { render(); return; }
    }
    fetch("data/stats.json", { cache: "no-cache" })
      .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); })
      .then(function (j) { data = j; render(); })
      .catch(function () {
        byId("st-cards").appendChild(el("p", { "class": "st-empty" }, "The numbers could not be loaded. Try again later."));
      });
  }

  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", start); }
  else { start(); }
})();
