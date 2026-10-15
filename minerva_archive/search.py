"""MiNERVA Archive search over its public JSON API.

Myrient shut down 31 March 2026; MiNERVA is the community continuation of
its whole catalogue, distributed as collection torrents. The search API
needs no key:

    GET /v1/api/rom/search?query=&offset=&tokenised=&group=&console=&region=
    -> [{"id", "full_path", "magnet", "so_id"}, ...]

Two properties of this source shape the provider:

**A magnet is per collection group, not per game.** One torrent covers a
whole dump ("TOSEC - Nintendo" holds thousands of zips). So the magnet is
carried in `source_id` -- the `torrent` capability resolves it to a
TorrentSource for handoff to the operator's client -- and rows sharing a
magnet collapse to one result, else a hundred `[a8]`/`[a9]` alternates of
one dump bury every other source.

**The API publishes no size and no seeder count.** `size_bytes` is left
None (unknown) rather than 0-as-tiny; the host's scoring treats an unknown
size as "no evidence either way", not "too small to be real".
"""

from urllib.parse import urlparse

from rom_hub_sdk import SearchProvider, SearchResult

ENDPOINT = "https://minerva-archive.org/v1/api/rom/search"
DETAIL = "https://minerva-archive.org/rom?id="
#: A full page is the API's "there is more" signal; it returns >100 when a
#: next page exists, so 100 is the page size to advance `offset` by.
PAGE = 100


def _title_of(full_path: str) -> str:
    """The filename at the end of a MiNERVA path, as the result's title.

    `full_path` is like `./TOSEC/Nintendo/Super Famicom/Games/Chrono
    Trigger (1995)(Square)(US).zip`. The scorer and the operator both want
    the game name, not the archive path, so the last component is the title.
    """
    path = (full_path or "").replace("\\", "/").strip()
    return path.rstrip("/").rsplit("/", 1)[-1] or path


def _info_hash(magnet: str) -> str:
    """The btih out of a magnet, for a stable source_id suffix.

    Two rows of one dump share a magnet; the hash is the torrent's identity,
    so it is what collapses them. Returns "" when the magnet names none, and
    the caller then falls back to the row id rather than dropping a result.
    """
    if not magnet.startswith("magnet:"):
        return ""
    for part in magnet.split("?", 1)[-1].split("&"):
        if part.startswith("xt=urn:btih:"):
            return part[len("xt=urn:btih:"):].lower()
    return ""


class Search(SearchProvider):
    def search(
        self, query: str, platform: str | None, limit: int
    ) -> list[SearchResult]:
        query = (query or "").strip().lower()
        if not query:
            return []

        cfg = self.ctx.config
        group = str(cfg.get("group") or "")
        console = str(cfg.get("console") or "")
        region = str(cfg.get("region") or "")
        tokenised = bool(cfg.get("tokenised"))
        try:
            max_pages = max(1, int(cfg.get("max_pages") or 1))
        except (TypeError, ValueError):
            max_pages = 1

        rows: list[dict] = []
        offset = 0
        for _ in range(max_pages):
            params: dict = {"query": query, "offset": offset}
            # Empty filters are omitted, not sent as "", so the API's own
            # defaults apply and the query string stays clean.
            if tokenised:
                params["tokenised"] = "true"
            if group:
                params["group"] = group
            if console:
                params["console"] = console
            if region:
                params["region"] = region
            response = self.ctx.http.get(ENDPOINT, params=params)
            if response.status_code != 200:
                # A non-200 is a hard failure of this page; surface what we
                # have rather than raise and lose earlier pages.
                break
            page = response.json()
            if not isinstance(page, list) or not page:
                break
            rows.extend(r for r in page if isinstance(r, dict))
            if len(page) < PAGE:
                break
            offset += PAGE

        return self._to_results(rows, limit)

    def _to_results(self, rows: list[dict], limit: int) -> list[SearchResult]:
        out: list[SearchResult] = []
        seen: set[str] = set()
        for row in rows:
            magnet = str(row.get("magnet") or "")
            full_path = str(row.get("full_path") or "")
            if not magnet.startswith("magnet:") or not full_path:
                continue
            # Collapse one dump's many alternates to a single result, keyed on
            # the torrent identity (its info-hash) with the row id as fallback.
            key = _info_hash(magnet) or f"id:{row.get('id')}"
            if key in seen:
                continue
            seen.add(key)
            title = _title_of(full_path)
            if not title:
                continue
            rom_id = row.get("id")
            out.append(SearchResult(
                source_id=magnet,
                title=title,
                # MiNERVA names no RomM platform in search results; the path's
                # vendor segment is not a reliable slug. Left None so the host
                # matches on title, exactly as it does for other sources.
                platform=None,
                size_bytes=None,          # not published -- unknown, not zero
                url=f"{DETAIL}{rom_id}" if rom_id is not None else None,
                extra={
                    "group": str(row.get("group") or ""),
                    "region": str(row.get("region") or ""),
                    "console": str(row.get("console") or ""),
                    "so_id": str(row.get("so_id") or ""),
                    # The whole path, so an operator can see which dump a
                    # collection torrent covers before grabbing gigabytes.
                    "path": full_path,
                },
            ))
            if len(out) >= limit:
                break
        return out
