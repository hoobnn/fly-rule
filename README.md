<div align="center">

# fly-rule

把 MetaCubeX meta-rules-dat、SukkaW（ruleset.skk.moe）和 Aethersailor 的分流规则汇总到一个 `release` 分支，Surge 和 mihomo 都能直接引用。

[![build](https://img.shields.io/github/actions/workflow/status/hoobnn/fly-rule/build.yml?branch=main&style=flat-square&label=build)](https://github.com/hoobnn/fly-rule/actions/workflows/build.yml)
[![release](https://img.shields.io/github/last-commit/hoobnn/fly-rule/release?style=flat-square&label=release)](https://github.com/hoobnn/fly-rule/tree/release)
[![Surge](https://img.shields.io/badge/Surge-RULE--SET%20%2F%20DOMAIN--SET-555?style=flat-square)](#surge)
[![mihomo](https://img.shields.io/badge/mihomo-rule--providers%20%C2%B7%20mrs-555?style=flat-square)](#mihomo)
[![license](https://img.shields.io/badge/license-AGPL--3.0-blue?style=flat-square)](LICENSE)

**简体中文** · [English](README.en.md)

</div>

MetaCubeX 只提供 mihomo / sing-box 格式的规则，Surge 无法直接使用。本项目负责格式转换与汇总，让 Surge 和 mihomo 共用同一套分流规则。
meta-rules-dat 的 geosite / geoip 每个类别都转成了 Surge `RULE-SET`；mihomo 这边提供 `.mrs`、`.yaml`、`.list` 三种格式。
上游每天同步一次，每次发布前都会经过语法、条数和实际加载三项检查。

## 适合谁用

- 想在 Surge 里用 MetaCubeX 的 geosite / geoip 分类（`cn`、`geolocation-!cn`、`openai`、`google`……），但上游没有 Surge 格式。
- 用 mihomo 的 `rule-providers`，想从一个地方引用 MetaCubeX、SukkaW、Aethersailor 三家的规则，URL 写法统一。
- Surge 和 mihomo 共用一套分流，两边各自需要能正常加载的版本。规则类型名的改写和 `DOMAIN-KEYWORD` 的取舍均已处理。
- 需要维护自定义规则：只需编写一份 classical 源文件，构建时自动生成 Surge 和 mihomo（含 mrs）共八份产物。

## 快速开始

所有产物都在 `release` 分支，raw URL 前缀是：

```text
https://raw.githubusercontent.com/hoobnn/fly-rule/release/
```

将下例中的 `Proxy` 替换为你的策略组名。所有域名规则都要放在 IP 规则之前，原因见[产物](#产物)一节。

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

`format` 要和文件后缀对应，`behavior` 要和目录对应，否则 mihomo 会加载失败：

| 目录 | 文件 | `behavior` | `format` |
| --- | --- | --- | --- |
| `metacubex/geosite/mihomo/` | `.mrs` / `.yaml` / `.list` | `domain` | `mrs` / `yaml` / `text` |
| `metacubex/geoip/mihomo/` | `.mrs` / `.yaml` / `.list` | `ipcidr` | `mrs` / `yaml` / `text` |
| `metacubex/geosite/mihomo-classical/` | `.yaml` / `.list` | `classical` | `yaml` / `text` |
| `sukkaw/mihomo/domainset/` | `.txt` | `domain` | `text` |
| `sukkaw/mihomo/non_ip/` | `.txt` | `classical` | `text` |
| `sukkaw/mihomo/ip/` | `.txt` | `ipcidr` | `text` |
| `aethersailor/rule-mihomo/` | `*_Domain.mrs` / `*_IP.mrs` | `domain` / `ipcidr` | `mrs` |

`custom/` 的引用方式见 [`custom/README.md`](custom/README.md#怎么引用)。

## 上游

| 上游 | 协议 | 处理 |
| --- | --- | --- |
| [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) | GPL-3.0 | 转换 + 镜像 |
| [SukkaLab/ruleset.skk.moe](https://github.com/SukkaLab/ruleset.skk.moe) | AGPL-3.0 | 原样镜像 |
| [Aethersailor/Custom_OpenClash_Rules](https://github.com/Aethersailor/Custom_OpenClash_Rules) | CC-BY-SA-4.0 | 镜像，并为两端各提供一份适配版 |

## 产物

所有产物位于 `release` 分支，路径为 `<上游>/<数据集>/<格式>/`：

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

规则顺序：所有域名规则都要排在 IP 规则之前。否则匹配到 IP 规则时会触发 DNS 解析，从而失去对 DNS 污染的防护。

支持直接引用属性变体，共 342 个，比如 `youtube@ads.conf`、`adobe@cn.conf`、`airchina@!cn.conf`。`@` 和 `!` 在 raw URL 里不用转义。

## 自定义规则

在 `custom/` 里写一份 classical 源文件，域名和 IP 可以混着写。构建时会生成 Surge 三份（混合 / 仅域名 / 仅 IP）和 mihomo 五份（一份 classical，domain 和 ipcidr 各一份 `.yaml` 加预编译的 `.mrs`），一共八份。
写法详见 [`custom/README.md`](custom/README.md)。

mihomo 推荐使用 `.mrs`：预编译格式，加载快、体积小。但 mrs 只支持 `domain` 和 `ipcidr`，不支持 `classical`（classical 里有 `PROCESS-NAME` 这类没法编译的规则）。因此全部使用 mrs 时，配置中不会出现 classical 规则。
相应地，`DOMAIN-KEYWORD` 无法在 mihomo 的 domain 规则中表达，会从 `-domain` 产物中移除。

修改 `custom/` 会触发独立的 CI（`custom.yml`），只重建自定义规则并直接替换 `release` 中的 `custom/`，不拉取上游，几秒钟内即可生效，无需等待每日定时构建。

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

两个 workflow 共用 `release-publish` 并发组，串行执行，不会同时推 `release` 互相覆盖。直接在 `release` 上的修改会被覆盖，请在 `main` 上修改。

## 发布前的检查

- `verify.py` 逐个文件核对：转换产物的条数和上游一致，镜像逐字节一致，并逐行检查是否有规则会被 Surge 跳过（类型白名单是用 `surge-cli --check` 实测出来的）。
- `loadcheck.py` 用 mihomo 实际加载 custom 和镜像规则集；加载条数少于文件中的条数，说明有规则被静默丢弃。
- `guard.py` 与上一次发布比对，某个类别消失或条数下降超过 50% 时阻止发布。

以上均为 CI 中的强制检查，未通过则不发布。镜像与上游逐字节一致，本项目无法修正其中的问题，因此镜像中的问题只告警，并记录在 CI 运行摘要中。

Aethersailor 的原样镜像 `rule/` 里有两端都加载不了的条目，只留作对照。Surge 请引用 `aethersailor/rule-surge/`，mihomo 请引用 `aethersailor/rule-mihomo/`，文件名和上游一样。

两端各有对方无法表达的规则，转换时的取舍如下：

| 规则 | Surge 产物 | mihomo domain / mrs |
| --- | --- | --- |
| `DOMAIN-KEYWORD` | 保留 | 表达不了：custom 里直接排除；Aethersailor 的 `*kw*` 按 geosite 已收录的域名展开 |
| `DOMAIN-REGEX`（geosite 的 regexp） | 不支持，跳过并在文件头注明 | 上游已排除 |
| `DST-PORT` / `SRC-IP-CIDR`（custom、Aethersailor） | 改写为 `DEST-PORT` / `SRC-IP` | classical 原样保留 |
| IPv6 写成 `IP-CIDR`（Aethersailor） | 改写为 `IP-CIDR6` | 原样（mihomo 两种都认） |

`surgecheck.py` 只能在安装了 Surge 的 Mac 上运行。修改转换逻辑或 Surge 升级后，需在本地运行一次，确认类型白名单没有变化。

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
另外 Aethersailor 的规则在 Surge 里要引用 `aethersailor/rule-surge/`，不要引用原样镜像 `aethersailor/rule/`。

### 可以 fork 之后加自己的规则吗？

可以。在 `custom/` 写 classical 源文件（见 [`custom/README.md`](custom/README.md)），在 fork 里打开 Actions，再把引用 URL 里的 `hoobnn` 换成你的用户名。请遵守下面各上游的协议。

## 许可与法律说明

### 本仓库

本仓库采用 [AGPL-3.0](LICENSE)。由于仓库中分发了 SukkaW 以 AGPL-3.0 授权的内容，而该协议具有传染性，整个仓库因此采用 AGPL-3.0。

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
- 留意代理服务商的服务条款。有些服务商规定，用了第三方规则文件就自动放弃 SLA 和技术支持，使用前请查阅相关条款。
- 规则数据里没有任何绕过技术。这里只是「哪些域名属于哪个服务」的分类数据，不主张也不指示流量该怎么处理，策略怎么映射完全由你自己的配置决定。
- 遵守当地法律。你所在的地区可能对网络流量转发有专门规定，合规由使用者自己负责。

如有上游作者认为本项目的镜像方式不妥，请提交 issue，相应内容会被及时移除。
