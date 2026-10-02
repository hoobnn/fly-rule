# fly-rule：Surge 与 mihomo（Clash Meta）分流规则

把 MetaCubeX meta-rules-dat、SukkaW（ruleset.skk.moe）和 Aethersailor 的分流规则汇总到一个 `release` 分支，Surge 和 mihomo 都能直接引用。

[![build](https://img.shields.io/github/actions/workflow/status/hoobnn/fly-rule/build.yml?branch=main&style=flat-square&label=build)](https://github.com/hoobnn/fly-rule/actions/workflows/build.yml)
[![release](https://img.shields.io/github/last-commit/hoobnn/fly-rule/release?style=flat-square&label=release)](https://github.com/hoobnn/fly-rule/tree/release)
[![Surge](https://img.shields.io/badge/Surge-RULE--SET%20%2F%20DOMAIN--SET-555?style=flat-square)](#surge)
[![mihomo](https://img.shields.io/badge/mihomo-rule--providers%20%C2%B7%20mrs-555?style=flat-square)](#mihomo)
[![license](https://img.shields.io/badge/license-AGPL--3.0-blue?style=flat-square)](LICENSE)

**简体中文** · [English](README.en.md)

我自己同时用 Surge 和 mihomo，想在两边用同一套分流规则，但 MetaCubeX 只出 mihomo / sing-box 格式，于是写了这个项目做转换和汇总。
meta-rules-dat 的 geosite / geoip 每个类别都转成了 Surge `RULE-SET`；mihomo 这边提供 `.mrs`、`.yaml`、`.list` 三种格式。
上游每天同步一次，每次发布前都要过语法、条数和实际加载三道检查。

## 适合谁用

- 想在 Surge 里用 MetaCubeX 的 geosite / geoip 分类（`cn`、`geolocation-!cn`、`openai`、`google`……），但上游没有 Surge 格式。
- 用 mihomo 的 `rule-providers`，想从一个地方引用 MetaCubeX、SukkaW、Aethersailor 三家的规则，URL 写法统一。
- Surge 和 mihomo 共用一套分流，两边各自需要能正常加载的版本。类型名改写和 `DOMAIN-KEYWORD` 的取舍已经处理好了。
- 自己维护一些自定义规则：写一份 classical 源文件，构建时自动生成 Surge 和 mihomo（含 mrs）共八份产物。

## 快速开始

所有产物都在 `release` 分支，raw URL 前缀是：

```text
https://raw.githubusercontent.com/hoobnn/fly-rule/release/
```

下面的 `Proxy` 换成你自己的策略组名。注意所有域名规则要放在所有 IP 规则前面，原因见[产物](#产物)一节。

### Surge

```ini
[Rule]
# --- 域名类 ---
DOMAIN-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/sukkaw/surge/domainset/reject.conf,REJECT
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/openai.conf,Proxy
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/google.conf,Proxy
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/cn.conf,DIRECT
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/geolocation-!cn.conf,Proxy
# --- IP 类（放在所有域名规则之后，并加 no-resolve）---
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geoip/surge/telegram.conf,Proxy,no-resolve
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geoip/surge/cn.conf,DIRECT,no-resolve
FINAL,Proxy
```

SukkaW 的 `domainset/` 用 `DOMAIN-SET` 引用，`non_ip/` 和 `ip/` 用 `RULE-SET`（`ip/` 要加 `no-resolve`）。

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

`format` 要和文件后缀对应，`behavior` 要和目录对应，写错的话 mihomo 会加载失败：

| 目录 | 文件 | `behavior` | `format` |
| --- | --- | --- | --- |
| `metacubex/geosite/mihomo/` | `.mrs` / `.yaml` / `.list` | `domain` | `mrs` / `yaml` / `text` |
| `metacubex/geoip/mihomo/` | `.mrs` / `.yaml` / `.list` | `ipcidr` | `mrs` / `yaml` / `text` |
| `metacubex/geosite/mihomo-classical/` | `.yaml` / `.list` | `classical` | `yaml` / `text` |
| `sukkaw/mihomo/domainset/` | `.txt` | `domain` | `text` |
| `sukkaw/mihomo/non_ip/` | `.txt` | `classical` | `text` |
| `sukkaw/mihomo/ip/` | `.txt` | `ipcidr` | `text` |
| `aethersailor/rule-mihomo/` | `*_Domain.mrs` / `*_IP.mrs` | `domain` / `ipcidr` | `mrs` |

`custom/` 怎么引用见 [`custom/README.md`](custom/README.md#怎么引用)。

## 上游

| 上游 | 协议 | 处理 |
| --- | --- | --- |
| [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) | GPL-3.0 | 转换 + 镜像 |
| [SukkaLab/ruleset.skk.moe](https://github.com/SukkaLab/ruleset.skk.moe) | AGPL-3.0 | 原样镜像 |
| [Aethersailor/Custom_OpenClash_Rules](https://github.com/Aethersailor/Custom_OpenClash_Rules) | CC-BY-SA-4.0 | 镜像，另外给两端各出一份适配版 |

## 产物

都在 `release` 分支，路径是 `<上游>/<数据集>/<格式>/`：

```text
metacubex/geosite/{surge,mihomo,mihomo-classical}/   1892 类
metacubex/geoip/{surge,mihomo}/                       260 类
metacubex/geo-lite-geosite/, geo-lite-geoip/           35 类
sukkaw/{surge,mihomo}/{domainset,non_ip,ip}/
aethersailor/rule/                                    上游原样，只作对照
aethersailor/rule-surge/                              .list 的 Surge 专用版
aethersailor/rule-mihomo/                             mihomo 专用版（同名文件）
custom/{surge,mihomo}/
```

`surge/` 给 Surge 用，`mihomo/` 给 mihomo 用（geosite 用 `behavior: domain`，geoip 用 `ipcidr`，`mihomo-classical/` 用 `classical`）。

关于顺序：所有域名规则都要排在 IP 规则前面。否则一旦匹配到 IP 规则就会触发 DNS 解析，DNS 污染的防护也就没了。

属性变体可以直接用，一共 342 个，比如 `youtube@ads.conf`、`adobe@cn.conf`、`airchina@!cn.conf`。`@` 和 `!` 在 raw URL 里不用转义。

## 自定义规则

在 `custom/` 里写一份 classical 源文件，域名和 IP 可以混着写。构建时会生成 Surge 三份（混合 / 仅域名 / 仅 IP）和 mihomo 五份（一份 classical，domain 和 ipcidr 各一份 `.yaml` 加预编译的 `.mrs`），一共八份。
写法详见 [`custom/README.md`](custom/README.md)。

mihomo 这边推荐用 `.mrs`，预编译过，加载快，文件也小。但 mrs 只支持 `domain` 和 `ipcidr`，不支持 `classical`（classical 里有 `PROCESS-NAME` 这类没法编译的规则）。所以如果全部用 mrs，配置里就不会有 classical。
代价是 `DOMAIN-KEYWORD` 在 mihomo 的 domain 侧表达不了，会从 `-domain` 产物里去掉。

改了 `custom/` 会触发单独的 CI（`custom.yml`），只重建自定义规则，直接替换 `release` 里的 `custom/`，不拉上游。几秒钟就能用上，不用等每天的定时构建。

## 构建

```bash
python3 scripts/build.py     # 同步所有上游（--only <key> 只构建一个，--offline 不联网）
python3 scripts/custom.py    # 只重建自定义规则
python3 scripts/mrs.py       # 把 custom 的 domain/ipcidr 产物编译成 mrs（需 mihomo）
python3 scripts/verify.py    # 语法 / 重复 / 无损门禁（--only-custom 只查 custom/）
python3 scripts/loadcheck.py # 用 mihomo 实际加载，核对条数（需 mihomo）
python3 scripts/surgecheck.py  # 用 Surge 解析器复核（仅限装了 Surge 的 Mac）
python3 scripts/guard.py --repo <user>/fly-rule
pnpm lint                    # ruff + markdownlint
```

全量构建大约 34 秒，不依赖第三方 Python 包。编译 mrs 需要 `mihomo` 可执行文件，CI 里按钉死的版本和校验和下载；本地没装的话 `mrs.py` 会跳过，不影响其他步骤。

CI 有两个 workflow，都发布到 `release`：

| workflow | 触发 | 做什么 |
| --- | --- | --- |
| `build.yml` | 每天 04:30 / 上游相关改动 | 重建全部产物，整个 `release` 换新 |
| `custom.yml` | `custom/`、`custom.py` 或 `mrs.py` 有改动 | 只替换 `release` 里的 `custom/` |

两个 workflow 共用 `release-publish` 并发组，串行执行，不会同时推 `release` 互相覆盖。直接在 `release` 上改的东西会被覆盖掉，要改请改 `main`。

## 发布前的检查

- `verify.py` 逐个文件核对：转换产物的条数和上游一致，镜像逐字节一致，并逐行检查 Surge 会不会跳过某条规则（类型白名单是用 `surge-cli --check` 实测出来的）。
- `loadcheck.py` 让 mihomo 真的加载一遍 custom 和镜像规则集，加载到的条数比文件里少，就说明有规则被悄悄丢了。
- `guard.py` 和上一次发布比对，某个类别消失或条数掉了 50% 以上就拦住不发。

这些在 CI 里都是硬性检查，不过就不发布。镜像和上游逐字节一致，有问题我这边也改不了，所以镜像里的问题只告警，写在 CI 运行摘要里。

Aethersailor 的原样镜像 `rule/` 里有两端都加载不了的条目，只留作对照。Surge 请引用 `aethersailor/rule-surge/`，mihomo 请引用 `aethersailor/rule-mihomo/`，文件名和上游一样。

两端都有对方表达不了的规则，转换时是这样取舍的：

| 规则 | Surge 产物 | mihomo domain / mrs |
| --- | --- | --- |
| `DOMAIN-KEYWORD` | 保留 | 表达不了：custom 里直接排除；Aethersailor 的 `*kw*` 按 geosite 已收录的域名展开 |
| `DOMAIN-REGEX`（geosite 的 regexp） | 不支持，跳过并在文件头注明 | 上游已排除 |
| `DST-PORT` / `SRC-IP-CIDR`（custom、Aethersailor） | 改写为 `DEST-PORT` / `SRC-IP` | classical 原样保留 |
| IPv6 写成 `IP-CIDR`（Aethersailor） | 改写为 `IP-CIDR6` | 原样（mihomo 两种都认） |

`surgecheck.py` 只能在装了 Surge 的 Mac 上跑。改了转换逻辑或者 Surge 升级之后，我会在本地跑一次，确认白名单没有变。

## 常见问题

### MetaCubeX meta-rules-dat 有 Surge 格式吗？

上游没有。这个项目把 `geo/geosite/classical/` 和 `geo/geoip/` 转成 Surge `RULE-SET`，放在 `metacubex/*/surge/`，文件名和上游类别同名（`cn.conf`、`geolocation-!cn.conf`、`youtube@ads.conf`……）。
每个文件头都写了上游路径、上游 commit 和规则数。Surge 不支持的 `DOMAIN-REGEX` 会被跳过，跳过的条数也写在文件头里。

### 多久更新一次？

`build.yml` 每天北京时间 04:30（UTC 20:30）同步全部上游，上游没变化就不发布。`custom/` 的改动由 `custom.yml` 单独发布，几秒钟就能用上。

### mihomo 该用 `.mrs`、`.yaml` 还是 `.list`？

优先用 `.mrs`，预编译、加载快、文件小。`.yaml` 和 `.list` 内容一样，想直接看规则内容时用它们比较方便。需要 `DOMAIN-KEYWORD` 这类非域名 / IP 规则时，只能用 classical（`mihomo-classical/`）。

### 规则在 Surge 里没生效，或者触发了 DNS 解析，怎么办？

先查顺序：域名类（`DOMAIN-SET` / geosite `RULE-SET`）要全部排在 IP 类前面，IP 类规则集要加 `no-resolve`。
另外 Aethersailor 的规则在 Surge 里要引用 `aethersailor/rule-surge/`，别引用原样镜像的 `aethersailor/rule/`。

### 可以 fork 之后加自己的规则吗？

可以。在 `custom/` 写 classical 源文件（见 [`custom/README.md`](custom/README.md)），在 fork 里打开 Actions，再把引用 URL 里的 `hoobnn` 换成你的用户名。请遵守下面各上游的协议。

## 许可与法律说明

### 本仓库

本仓库用 [AGPL-3.0](LICENSE)。选这个协议是因为仓库里分发了 SukkaW 的 AGPL-3.0 内容，该协议有传染性，整个仓库只能跟着用 AGPL-3.0。

各上游内容的著作权归原作者。这个项目只做格式转换和镜像，不主张任何权利。转换产物的文件头里都写了来源仓库和上游 commit。

### 各上游协议

| 上游 | 协议 | 要求 |
| --- | --- | --- |
| MetaCubeX/meta-rules-dat | GPL-3.0 | 署名、保留协议、衍生作品以同协议开源 |
| SukkaLab/ruleset.skk.moe | AGPL-3.0 | 同上，并且通过网络提供服务也要开源 |
| Aethersailor/Custom_OpenClash_Rules | CC-BY-SA-4.0 | 署名、相同方式共享 |

例外：SukkaW 的 `sukkaw/surge/ip/china_ip.conf` 和 `sukkaw/mihomo/ip/china_ip.txt` 按作者声明使用 CC BY-SA 2.0，不适用 AGPL-3.0。

SukkaW 在 README 里明确表示欢迎搭镜像，并要求从 `SukkaLab/ruleset.skk.moe` 同步，本项目就是这么做的。

### 使用前请注意

- 不提供任何担保。规则可能过时、误判，也可能导致连接异常，风险自负。作者不对任何损失负责，包括但不限于网络不可用、服务被封禁、数据丢失。
- 留意代理服务商的服务条款。有些服务商规定，用了第三方规则文件就自动放弃 SLA 和技术支持，用之前先看一下你的条款。
- 规则数据里没有任何绕过技术。这里只是「哪些域名属于哪个服务」的分类数据，不主张也不指示流量该怎么处理，策略怎么映射完全由你自己的配置决定。
- 遵守当地法律。你所在的地区可能对网络流量转发有专门规定，合规由使用者自己负责。

如果哪位上游作者觉得这里的镜像方式不妥，请提 issue，我会马上移除对应部分。
