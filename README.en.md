<div align="center">

# fly-rule

Routing rules from MetaCubeX meta-rules-dat, SukkaW's ruleset.skk.moe and Aethersailor's Custom_OpenClash_Rules, collected on one `release` branch that Surge and mihomo can both reference directly.

[![build](https://img.shields.io/github/actions/workflow/status/hoobnn/fly-rule/build.yml?branch=main&style=flat-square&label=build)](https://github.com/hoobnn/fly-rule/actions/workflows/build.yml)
[![release](https://img.shields.io/github/last-commit/hoobnn/fly-rule/release?style=flat-square&label=release)](https://github.com/hoobnn/fly-rule/tree/release)
[![Surge](https://img.shields.io/badge/Surge-RULE--SET%20%2F%20DOMAIN--SET-555?style=flat-square)](#surge)
[![mihomo](https://img.shields.io/badge/mihomo-rule--providers%20%C2%B7%20mrs-555?style=flat-square)](#mihomo)
[![license](https://img.shields.io/badge/license-AGPL--3.0-blue?style=flat-square)](LICENSE)

[简体中文](README.md) · **English**

</div>

MetaCubeX only publishes mihomo / sing-box formats, which Surge cannot load.
This project converts and collects them so Surge and mihomo can share the same
routing rules (分流规则). Every meta-rules-dat geosite / geoip category is
available as a Surge `RULE-SET`; on the mihomo side you get `.mrs`, `.yaml` and
`.list`. Upstreams sync once a day, and nothing is published until it passes
syntax, rule-count and real-load checks.

## Who it's for

- You want MetaCubeX geosite / geoip categories (`cn`, `geolocation-!cn`, `openai`, `google`, …) in Surge, and upstream has no Surge format.
- You use mihomo (Clash Meta) `rule-providers` and want MetaCubeX, SukkaW and Aethersailor rules from one place, with URLs that follow one pattern.
- You share one routing setup between Surge and mihomo, and each side needs a version it can actually load. Rule type renames and the `DOMAIN-KEYWORD` trade-off are already handled.
- You keep some rules of your own: write one classical source file and the build produces eight Surge and mihomo files from it, mrs included.

## Quick start

Everything lives on the `release` branch. The raw URL prefix is:

```text
https://raw.githubusercontent.com/hoobnn/fly-rule/release/
```

Replace `Proxy` below with your own policy group. All domain rules must come before all IP rules; [Outputs](#outputs) explains why.

### Surge

```ini
[Rule]
# --- domain rules ---
DOMAIN-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/sukkaw/surge/domainset/reject.conf,REJECT
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/openai.conf,Proxy
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/google.conf,Proxy
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/cn.conf,DIRECT
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/geolocation-!cn.conf,Proxy
# --- IP rules (after every domain rule, with no-resolve) ---
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geoip/surge/telegram.conf,Proxy,no-resolve
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geoip/surge/cn.conf,DIRECT,no-resolve
FINAL,Proxy
```

SukkaW's `domainset/` files are referenced with `DOMAIN-SET`; `non_ip/` and `ip/` with `RULE-SET` (add `no-resolve` to `ip/`).

### mihomo

```yaml
rule-providers:
  reject:
    type: http
    behavior: domain
    format: text
    interval: 86400
    url: https://raw.githubusercontent.com/hoobnn/fly-rule/release/sukkaw/mihomo/domainset/reject.txt
  openai:
    type: http
    behavior: domain
    format: mrs
    interval: 86400
    url: https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/mihomo/openai.mrs
  cn:
    type: http
    behavior: domain
    format: mrs
    interval: 86400
    url: https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/mihomo/cn.mrs
  geolocation-not-cn:
    type: http
    behavior: domain
    format: mrs
    interval: 86400
    url: "https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/mihomo/geolocation-!cn.mrs"
  telegram-ip:
    type: http
    behavior: ipcidr
    format: mrs
    interval: 86400
    url: https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geoip/mihomo/telegram.mrs
  cn-ip:
    type: http
    behavior: ipcidr
    format: mrs
    interval: 86400
    url: https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geoip/mihomo/cn.mrs

rules:
  - RULE-SET,reject,REJECT
  - RULE-SET,openai,Proxy
  - RULE-SET,cn,DIRECT
  - RULE-SET,geolocation-not-cn,Proxy
  - RULE-SET,telegram-ip,Proxy,no-resolve
  - RULE-SET,cn-ip,DIRECT,no-resolve
  - MATCH,Proxy
```

`format` must follow the file extension and `behavior` must match the directory, otherwise mihomo fails to load the provider:

| Directory | Files | `behavior` | `format` |
| --- | --- | --- | --- |
| `metacubex/geosite/mihomo/` | `.mrs` / `.yaml` / `.list` | `domain` | `mrs` / `yaml` / `text` |
| `metacubex/geoip/mihomo/` | `.mrs` / `.yaml` / `.list` | `ipcidr` | `mrs` / `yaml` / `text` |
| `metacubex/geosite/mihomo-classical/` | `.yaml` / `.list` | `classical` | `yaml` / `text` |
| `sukkaw/mihomo/domainset/` | `.txt` | `domain` | `text` |
| `sukkaw/mihomo/non_ip/` | `.txt` | `classical` | `text` |
| `sukkaw/mihomo/ip/` | `.txt` | `ipcidr` | `text` |
| `aethersailor/rule-mihomo/` | `*_Domain.mrs` / `*_IP.mrs` | `domain` / `ipcidr` | `mrs` |

For `custom/`, see [`custom/README.md`](custom/README.md) (Chinese).

## Upstreams

| Upstream | License | Handling |
| --- | --- | --- |
| [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) | GPL-3.0 | converted + mirrored |
| [SukkaLab/ruleset.skk.moe](https://github.com/SukkaLab/ruleset.skk.moe) | AGPL-3.0 | mirrored as-is |
| [Aethersailor/Custom_OpenClash_Rules](https://github.com/Aethersailor/Custom_OpenClash_Rules) | CC-BY-SA-4.0 | mirrored + an adapted copy for each client |

## Outputs

All on the `release` branch, laid out as `<upstream>/<dataset>/<format>/`:

```text
metacubex/geosite/{surge,mihomo,mihomo-classical}/   1892 categories
metacubex/geoip/{surge,mihomo}/                       260 categories
metacubex/geo-lite-geosite/, geo-lite-geoip/           35 categories
sukkaw/{surge,mihomo}/{domainset,non_ip,ip}/
aethersailor/rule/                                    upstream as-is, reference only
aethersailor/rule-surge/                              Surge-specific build of the .list files
aethersailor/rule-mihomo/                             mihomo-specific build (same file names)
custom/{surge,mihomo}/
```

`surge/` is for Surge and `mihomo/` for mihomo (geosite uses `behavior: domain`,
geoip uses `ipcidr`, `mihomo-classical/` uses `classical`).

On ordering: put every domain rule before every IP rule. Once an IP rule is
evaluated, a DNS lookup happens, and you lose the protection against DNS
poisoning.

Attribute variants can be used directly, 342 in total: `youtube@ads.conf`,
`adobe@cn.conf`, `airchina@!cn.conf`. `@` and `!` need no escaping in raw URLs.

## Custom rules

Write one classical source file in `custom/` (domains and IPs mixed). The build
derives three Surge files (mixed / domain-only / IP-only) and five mihomo files
(one classical, plus `.yaml` and precompiled `.mrs` for both domain and
ipcidr), eight in total. See [`custom/README.md`](custom/README.md) (Chinese).

On mihomo, `.mrs` is recommended: it's precompiled, loads fast and is small. mrs
only supports `domain` and `ipcidr`, not `classical` (classical can contain rules
like `PROCESS-NAME` that cannot be compiled), so referencing only mrs means no
classical in your config. The trade-off is that `DOMAIN-KEYWORD` cannot be
expressed on mihomo's domain side and is excluded from the `-domain` outputs.

Changes under `custom/` trigger a separate CI workflow (`custom.yml`) that
rebuilds only the custom rules and replaces `custom/` on `release` in place,
without pulling upstreams. They are available within seconds; no need to wait
for the daily build.

## Build

```bash
python3 scripts/build.py     # sync all upstreams (--only <key> for one, --offline for no network)
python3 scripts/custom.py    # rebuild custom rules only
python3 scripts/mrs.py       # compile custom domain/ipcidr outputs to mrs (needs mihomo)
python3 scripts/verify.py    # syntax / duplicate / lossless gate (--only-custom checks custom/ only)
python3 scripts/loadcheck.py # load with mihomo and compare rule counts (needs mihomo)
python3 scripts/surgecheck.py  # re-check with Surge's parser (Macs with Surge only)
python3 scripts/guard.py --repo <user>/fly-rule
pnpm lint                    # ruff + markdownlint
```

A full build takes about 34 seconds with no third-party Python dependencies
(mrs needs the `mihomo` binary; CI downloads a pinned version and checksum.
Without it locally, `mrs.py` is skipped and the rest of the build still runs).

Two CI workflows publish to `release`:

| Workflow | Trigger | What it does |
| --- | --- | --- |
| `build.yml` | daily at 04:30 UTC+8 / upstream-related changes | rebuilds everything and replaces the whole `release` branch |
| `custom.yml` | changes to `custom/`, `custom.py` or `mrs.py` | replaces only `custom/` on `release` |

Both share the `release-publish` concurrency group and run serially, so they
never overwrite each other's pushes to `release`. Anything edited on `release`
gets overwritten, so change `main` instead.

## Checks before publishing

- `verify.py` goes file by file: converted outputs must match upstream rule
  counts, mirrors must be byte-identical, and every line is checked for whether
  Surge would skip it (the type whitelist was measured with `surge-cli --check`).
- `loadcheck.py` has mihomo actually load the custom and mirrored rule sets. If
  it loads fewer rules than the file contains, something was silently dropped.
- `guard.py` compares against the previous publish and stops it if a category
  disappears or a rule count drops by more than 50%.

In CI these are hard checks: if one fails, nothing is published. Mirrors are
byte-identical to upstream and cannot be fixed here, so problems in mirrors
are only reported as warnings in the CI run summary.

Aethersailor's as-is mirror `rule/` has entries neither client can load and is
kept for reference only. In Surge, reference `aethersailor/rule-surge/`; in
mihomo, `aethersailor/rule-mihomo/`. File names match upstream.

Each client has rules the other can't express. Conversion trade-offs:

| Rule | Surge output | mihomo domain / mrs |
| --- | --- | --- |
| `DOMAIN-KEYWORD` | kept | not expressible: excluded for custom; Aethersailor's `*kw*` expanded to domains already in geosite |
| `DOMAIN-REGEX` (geosite regexp) | unsupported, skipped and noted in the file header | already excluded upstream |
| `DST-PORT` / `SRC-IP-CIDR` (custom, Aethersailor) | rewritten to `DEST-PORT` / `SRC-IP` | classical unchanged |
| IPv6 written as `IP-CIDR` (Aethersailor) | rewritten to `IP-CIDR6` | unchanged (mihomo accepts both) |

`surgecheck.py` only runs on a Mac with Surge installed. Run it locally after
changing conversion logic or upgrading Surge, to make sure the whitelist hasn't
changed.

## FAQ

### Does MetaCubeX meta-rules-dat have a Surge format?

Not upstream. This project converts `geo/geosite/classical/` and `geo/geoip/`
into Surge `RULE-SET` files under `metacubex/*/surge/`, named after the upstream
categories (`cn.conf`, `geolocation-!cn.conf`, `youtube@ads.conf`, …). Each file
header records the upstream path, upstream commit and rule count;
`DOMAIN-REGEX` rules, which Surge doesn't support, are skipped and counted in
the header.

### How often is it updated?

`build.yml` syncs all upstreams daily at 20:30 UTC (04:30 UTC+8) and skips
publishing when nothing changed. Changes to `custom/` are published separately
by `custom.yml` within seconds.

### Should mihomo use `.mrs`, `.yaml` or `.list`?

Prefer `.mrs`: precompiled, fast to load, small. `.yaml` and `.list` hold the
same rules and are handy when you want to read them. For `DOMAIN-KEYWORD` and
other non-domain / non-IP rules, use classical (`mihomo-classical/`).

### Why doesn't a rule work in Surge, or why does it trigger DNS resolution?

Check the order: every domain rule (`DOMAIN-SET` / geosite `RULE-SET`) must come
before every IP rule, and IP rule sets need `no-resolve`. For Aethersailor rules
in Surge, reference `aethersailor/rule-surge/`, not the as-is mirror
`aethersailor/rule/`.

### Can I fork it and add my own rules?

Yes. Write classical source files in `custom/` (see
[`custom/README.md`](custom/README.md)), enable Actions in your fork, and
replace `hoobnn` in the URLs with your username. Follow the upstream licenses
below.

## Disclaimer

- This project provides rule data only. It does not provide any proxy service,
  servers, subscriptions or client software.
- No warranty. Rules may be outdated, misclassify, or break connections; use
  at your own risk. The author is not liable for any loss, including but not
  limited to network outages, blocked services, or data loss.
- Check your proxy provider's terms. Some providers state that using third-party
  rule files waives their SLA and technical support. Read your terms first.
- The rule data contains no circumvention technology. This project is only
  classification data about which domains belong to which service; it neither
  asserts nor instructs how any traffic should be handled; policy mapping is
  entirely up to your configuration.
- Follow local law. This project is for learning and researching traffic
  routing only, and must not be used for any purpose that breaks the laws or
  regulations of your country or region. Your jurisdiction may regulate network
  traffic forwarding; compliance is your own responsibility, and the author is
  not responsible for how you use it or the consequences.

If any upstream author considers the way this project mirrors their work
inappropriate, please open an issue and the corresponding part will be
removed promptly.

## License

### This repository

[AGPL-3.0](LICENSE). The repository redistributes SukkaW's AGPL-3.0 content,
and that license is copyleft, so the whole repository has to use AGPL-3.0 too.

Copyright in upstream content belongs to its original authors. This project only
converts formats and mirrors, and claims no rights. Every converted file header
records the source repository and upstream commit.

### Upstream licenses

| Upstream | License | Requirements |
| --- | --- | --- |
| MetaCubeX/meta-rules-dat | GPL-3.0 | attribution, keep the license, derivatives open-sourced under the same license |
| SukkaLab/ruleset.skk.moe | AGPL-3.0 | same as above, and providing it as a network service also requires releasing source |
| Aethersailor/Custom_OpenClash_Rules | CC-BY-SA-4.0 | attribution, share-alike |

Exception: SukkaW's `sukkaw/surge/ip/china_ip.conf` and
`sukkaw/mihomo/ip/china_ip.txt` are licensed CC BY-SA 2.0 per their
author's statement, not AGPL-3.0.

SukkaW's README explicitly welcomes mirrors and asks that they sync from
`SukkaLab/ruleset.skk.moe`, which is exactly how this project mirrors it.
