# rom-hub-minerva

**MiNERVA Archive** as a [ROM Hub](https://github.com/BlizzHacker/rom-hub) plugin — the community continuation of Myrient (shut down 31 March 2026), which archives Myrient's entire catalogue and distributes it as collection torrents through a public, keyless JSON API.

This is a *plugin*: a sandboxed subprocess that declares its capabilities and its network allowlist in `manifest.toml` and never opens a socket itself. Nothing about it is welded into ROMarr, RomM, or any other host — any host that speaks the ROM Hub plugin protocol gets MiNERVA search by installing this repo.

## Capabilities

| Capability | What it does |
|---|---|
| `search` | Queries `GET /v1/api/rom/search` with MiNERVA's own filter vocabulary (`group`, `console`, `region`, `tokenised`) and 100-row offset pagination. One result per collection torrent: rows sharing a magnet (`[a8]`/`[a9]` alternates of one dump) collapse, so one giant torrent doesn't bury every other source. |
| `torrent` | MiNERVA's magnets arrive bare (no trackers — DHT-only). `resolve()` keeps the info-hash, appends twelve well-known public trackers (every host declared in the manifest, because the Hub gates each `tr=` against that list), and returns a `TorrentSource` the host validates and hands to your torrent client. |

No `importer`: MiNERVA distributes by torrent only, and the Hub is deliberately not a torrent client — the host hands the magnet off to yours (qBittorrent, Transmission, Deluge).

## Install

```sh
rom-hub plugin install https://github.com/BlizzHacker/rom-hub-minerva
```

In ROMarr: **Settings → Hub → Plugins** shows it like any other; enabled plugins join Interactive Search and the request pipeline automatically.

## Config

| Key | Default | Meaning |
|---|---|---|
| `group` | `""` | Only this dump group (e.g. `TOSEC`, `No-Intro`, `Redump` — values from MiNERVA's filter bar) |
| `console` | `""` | Only this console (MiNERVA's own console names) |
| `region` | `""` | Only this region (e.g. `USA`) |
| `tokenised` | `false` | Match each query word separately instead of the whole phrase — better recall, more noise |
| `max_pages` | `1` | Search pages to walk (100 rows each) |

## Things worth knowing

- **A torrent is a whole dump group, not one game.** "TOSEC – Nintendo" is one torrent holding thousands of zips. The search result names the exact file (`extra.path`), but grabbing it grabs the collection. This is MiNERVA's distribution model, not a plugin limitation.
- **The API is slow** (20–25s per query, measured live). Hosts should allow ≥60s for plugin HTTP.
- **No sizes, no seeder counts** in search results. `size_bytes` is `None` — unknown, never fabricated.
- The API publishes no per-file download; the magnet is the only route.

## Tests

```sh
python -m pytest tests/ -q     # needs rom_hub_sdk installed (the ROMarr venv has it)
```

16 tests: query/filters/pagination/dedupe against canned API shapes, magnet rebuild + refusal paths, and the decisive one — the Hub's own `check_magnet` gate accepts what `resolve()` returns, with every declared tracker surviving.

## License

MIT.
