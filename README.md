# YT-DNS Tracker

> Automatically collect YouTube-related DNS domains from AdGuard Home and publish them to GitHub — ready to use as an OPNsense URL Table alias for policy routing through a VPN/tunnel.

## How it works

```
AdGuard Home query log
        │
        ▼  (every N minutes)
  yt-dns-tracker
        │  filters ~20 YouTube/Google CDN patterns
        ▼
  Accumulated domain list
        │
        ▼  GitHub API push
  raw.githubusercontent.com/…/youtube_domains.txt
        │
        ▼  OPNsense URL Table alias (auto-refreshed)
  Policy route → tunnel / VPN
```

## One-command install (Debian / Ubuntu)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/yt-dns-tracker/main/install.sh)
```

Then open **http://\<your-vm-ip\>:8080** and configure:

| Field | Example |
|---|---|
| AdGuard Home URL | `http://192.168.1.5:3000` |
| AdGuard username/password | your AdGuard credentials |
| GitHub Token | a PAT with `repo` scope |
| GitHub Repo | `yourname/yt-domains` |
| File path | `youtube_domains.txt` |
| Poll interval | `30` (minutes) |

Hit **Sync Now** — done.

## OPNsense configuration

1. **Firewall → Aliases → Add**
   - Type: `URL Table (Hosts)`
   - Name: `youtube_domains`
   - URL: `https://raw.githubusercontent.com/YOUR_USERNAME/yt-domains/main/youtube_domains.txt`
   - Refresh: `43200` (12 h)

2. **Firewall → Rules** — create a rule matching `youtube_domains` alias, set gateway to your tunnel interface.

## Docker management

```bash
# View live logs
docker compose logs -f yt-dns-tracker

# Stop
docker compose down

# Update
git pull && docker compose up -d --build
```

## Tracked domain patterns

| Pattern | Covers |
|---|---|
| `*.youtube.com` | Main site, API, embeds |
| `*.ytimg.com` | Thumbnails, images |
| `*.googlevideo.com` | Video streaming CDN (incl. dynamic `rr*---sn-*` nodes) |
| `*.ggpht.com` / `*.gvt1.com` | Avatar / asset CDN |
| `*.youtubei.googleapis.com` | Mobile / TV API |
| `youtu.be` | Short links |
| `*.youtubekids.com` etc. | Sibling products |

Domains **accumulate** across syncs — the list only grows unless you clear the cache from the UI.

## License

MIT
