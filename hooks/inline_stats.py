"""Put data/stats.json into the page, so the numbers show without a second request
(and the page still works where fetching a file is blocked). The file is also
published as it is, for anyone who wants the raw numbers."""

import json
from pathlib import Path

MARK = '<script id="st-data" type="application/json"></script>'


def on_page_content(html, page, config, files):
    if MARK not in html:
        return html
    path = Path(config["docs_dir"]) / "data" / "stats.json"
    if not path.exists():
        return html
    data = json.dumps(json.loads(path.read_text()), separators=(",", ":"))
    data = data.replace("</", "<\\/")                 # never close the script tag early
    return html.replace(MARK, f'<script id="st-data" type="application/json">{data}</script>')
