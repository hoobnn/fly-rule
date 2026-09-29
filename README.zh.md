# fly-rule — Surge 与 mihomo 分流规则集合

**把 MetaCubeX meta-rules-dat、SukkaW（ruleset.skk.moe）、Aethersailor 的分流规则聚合到一个 `release` 分支，Surge 与 mihomo（Clash Meta）都能直接引用。**

[![build](https://img.shields.io/github/actions/workflow/status/hoobnn/fly-rule/build.yml?branch=main&style=flat-square&label=build)](https://github.com/hoobnn/fly-rule/actions/workflows/build.yml)
[![release](https://img.shields.io/github/last-commit/hoobnn/fly-rule/release?style=flat-square&label=release)](https://github.com/hoobnn/fly-rule/tree/release)
[![Surge](https://img.shields.io/badge/Surge-RULE--SET%20%2F%20DOMAIN--SET-555?style=flat-square)](#surge)
[![mihomo](https://img.shields.io/badge/mihomo-rule--providers%20%C2%B7%20mrs-555?style=flat-square)](#mihomo)
[![license](https://img.shields.io/badge/license-AGPL--3.0-blue?style=flat-square)](LICENSE)

简体中文 · [English](README.md)

聚合多个上游的分流规则到 `release` 分支，Surge 与 mihomo 都能直接引用。
MetaCubeX 不出 Surge 格式，由本项目转换：meta-rules-dat 的 geosite / geoip
全部类别都有 Surge `RULE-SET` 版，mihomo 侧同时提供 `.mrs`、`.yaml`、`.list`。
每日自动同步上游，发布前经过语法、条数与实际加载门禁。

## 适用场景

- 想在 **Surge** 里用 MetaCubeX 的 **geosite / geoip** 分类（`cn`、`geolocation-!cn`、`openai`、`google`……），但上游只有 mihomo / sing-box 格式。
- 用 **mihomo（Clash Meta）** 的 `rule-providers`，想从一个地方引用 MetaCubeX、SukkaW、Aethersailor 三家的规则，URL 风格统一。
- 在 Surge 和 mihomo 之间**共用同一套分流规则**，两端各拿到自己能正确加载的版本（类型名改写、`DOMAIN-KEYWORD` 取舍都已处理）。
- 维护自己的**自定义规则**：写一份 classical 源文件，自动派生 Surge 与 mihomo（含 mrs）八份产物。

## 快速开始

所有产物都在 `release` 分支，raw URL 前缀是：

```text
https://raw.githubusercontent.com/hoobnn/fly-rule/release/
```

下面的 `Proxy` 换成你自己的策略组名。**所有域名规则必须放在所有 IP 规则之前**（原因见[产物](#产物)）。

### Surge

```ini
[Rule]
# —— 域名类 ——
DOMAIN-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/sukkaw/surge/domainset/reject.conf,REJECT
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/openai.conf,Proxy
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/google.conf,Proxy
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/cn.conf,DIRECT
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geosite/surge/geolocation-!cn.conf,Proxy
# —— IP 类（放在所有域名规则之后，并加 no-resolve）——
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geoip/surge/telegram.conf,Proxy,no-resolve
RULE-SET,https://raw.githubusercontent.com/hoobnn/fly-rule/release/metacubex/geoip/surge/cn.conf,DIRECT,no-resolve
FINAL,Proxy
```

SukkaW 的 `domainset/` 用 `DOMAIN-SET` 引用，`non_ip/` 与 `ip/` 用 `RULE-SET`（`ip/` 加 `no-resolve`）。

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

`format` 必须跟着文件后缀走，`behavior` 必须与目录对应，写错 mihomo 会加载失败：

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
| [SukkaLab/ruleset.skk.moe](https://github.com/SukkaLab/ruleset.skk.moe) | AGPL-3.0 | 纯镜像 |
| [Aethersailor/Custom_OpenClash_Rules](https://github.com/Aethersailor/Custom_OpenClash_Rules) | CC-BY-SA-4.0 | 镜像 + 两端各出一份适配版 |

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

`surge/` 给 Surge，`mihomo/` 给 mihomo（geosite 用 `behavior: domain`，
geoip 用 `ipcidr`，`mihomo-classical/` 用 `classical`）。

**顺序**：所有域名规则必须放在所有 IP 规则之前，否则匹配 IP 规则时会触发
DNS 解析，失去 DNS 污染保护。

属性变体直接可用，共 342 个：`youtube@ads.conf`、`adobe@cn.conf`、
`airchina@!cn.conf`。`@` 和 `!` 在 raw URL 里无需转义。

## 自定义规则

在 `custom/` 写一份 classical 源文件（域名与 IP 混写），构建时自动派生
Surge 三份（混写 / 仅域名 / 仅 IP）与 mihomo 五份（classical 一份，domain 与
ipcidr 各含 `.yaml` 和预编译 `.mrs`），共八份。
详见 [`custom/README.md`](custom/README.md)。

mihomo 侧推荐用 `.mrs`：预编译、加载快、文件小。**mrs 只支持 `domain` 与
`ipcidr`，不支持 `classical`**（后者含 `PROCESS-NAME` 这类无法编译的规则），
所以全部引用 mrs 也就意味着配置里不会出现 classical。代价是 `DOMAIN-KEYWORD`
在 mihomo 的 domain 侧无法表达，会被排除出 `-domain` 产物。

改动 `custom/` 会触发单独的 CI（`custom.yml`），只重建自定义规则并就地替换
`release` 里的 `custom/`，不拉上游，约数秒可用，不必等每日构建。

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

全量约 34 秒，无第三方 Python 依赖（mrs 需要 `mihomo` 可执行文件，CI 里按钉死
的版本与校验和下载；本地没装时 `mrs.py` 跳过，不阻塞其余构建）。

CI 有两个 workflow，都发布到 `release`：

| workflow | 触发 | 做什么 |
| --- | --- | --- |
| `build.yml` | 每日 04:30 / 上游相关改动 | 重建全部产物，整棵 `release` 换新 |
| `custom.yml` | `custom/`、`custom.py` 或 `mrs.py` 改动 | 只替换 `release` 里的 `custom/` |

两者共用 `release-publish` 并发组，串行执行，避免同时推 `release` 互相覆盖。
`release` 上改东西会被覆盖，要改请改 `main`。

## 门禁

`verify.py` 逐文件核对转换产物条数与上游一致、镜像逐字节一致，并逐行检查
Surge 侧会不会跳过（类型白名单按 `surge-cli --check` 实测）；
`loadcheck.py` 让 mihomo 实际加载 custom 与镜像规则集，加载条数少于文件条数
即判为被静默丢弃；
`guard.py` 与上次发布比对，类别消失或条数暴跌超 50% 就拦下发布。CI 里都是硬门禁。
镜像与上游逐字节一致、修不了，其中的问题只告警，出现在 CI 运行摘要里。
Aethersailor 的镜像 `rule/` 两端都有加载不了的条目，只作对照：Surge 引用
`aethersailor/rule-surge/`，mihomo 引用 `aethersailor/rule-mihomo/`，文件名与上游相同。

两端都有对方表达不了的规则，转换时的取舍：

| 规则 | Surge 产物 | mihomo domain / mrs |
| --- | --- | --- |
| `DOMAIN-KEYWORD` | 保留 | 表达不了：custom 排除；Aethersailor 的 `*kw*` 按 geosite 已收录域名展开 |
| `DOMAIN-REGEX`（geosite 的 regexp） | 不支持，跳过并在文件头注明 | 上游已排除 |
| `DST-PORT` / `SRC-IP-CIDR`（custom、Aethersailor） | 改写为 `DEST-PORT` / `SRC-IP` | classical 原样 |
| IPv6 写成 `IP-CIDR`（Aethersailor） | 改写为 `IP-CIDR6` | 原样（mihomo 两种都接受） |

`surgecheck.py` 只能在装了 Surge 的 Mac 上跑，改了转换逻辑或 Surge 升级后
本地跑一次，确认白名单没有漂移。

## 常见问题

### MetaCubeX meta-rules-dat 有 Surge 格式吗？

上游没有。本项目把 `geo/geosite/classical/` 与 `geo/geoip/` 转成 Surge
`RULE-SET`，放在 `metacubex/*/surge/`，文件名与上游类别同名（`cn.conf`、
`geolocation-!cn.conf`、`youtube@ads.conf`……）。每个文件头注明上游路径、上游
commit 与规则数；Surge 不支持的 `DOMAIN-REGEX` 会跳过并在文件头注明条数。

### 多久更新一次？

`build.yml` 每日北京时间 04:30（UTC 20:30）同步全部上游；上游没变化就不发布。
`custom/` 的改动由 `custom.yml` 单独发布，约数秒可用。

### mihomo 该用 `.mrs`、`.yaml` 还是 `.list`？

优先 `.mrs`：预编译、加载快、文件小。`.yaml` 与 `.list` 内容相同，适合想直接
看规则内容时用。需要 `DOMAIN-KEYWORD` 等非域名 / IP 规则时，只能用 classical
（`mihomo-classical/`）。

### 为什么我的规则在 Surge 里没生效，或者触发了 DNS 解析？

检查顺序：域名类（`DOMAIN-SET` / geosite `RULE-SET`）必须全部排在 IP 类之前，
IP 类规则集要加 `no-resolve`。Aethersailor 的规则 Surge 要引用
`aethersailor/rule-surge/`，不要引用原样镜像的 `aethersailor/rule/`。

### 可以 fork 后加自己的规则吗？

可以。在 `custom/` 写 classical 源文件（见 [`custom/README.md`](custom/README.md)），
在 fork 里启用 Actions，并把引用 URL 里的 `hoobnn` 换成你的用户名。
遵守下方各上游协议。

## 许可与法律说明

### 本仓库

**[AGPL-3.0](LICENSE)**。这不是自由选择的结果 —— 本仓库分发 AGPL-3.0 的内容
（SukkaW），该协议具有传染性，因此整体必须以 AGPL-3.0 分发。

各上游内容的著作权归原作者所有，本项目仅做格式转换与镜像，不主张任何权利。
转换产物的文件头均注明来源仓库与上游 commit。

### 各上游协议

| 上游 | 协议 | 要求 |
| --- | --- | --- |
| MetaCubeX/meta-rules-dat | GPL-3.0 | 署名、保留协议、衍生作品同协议开源 |
| SukkaLab/ruleset.skk.moe | AGPL-3.0 | 同上，且**通过网络提供服务也须开源** |
| Aethersailor/Custom_OpenClash_Rules | CC-BY-SA-4.0 | 署名、相同方式共享 |

例外：SukkaW 的 `sukkaw/surge/ip/china_ip.conf` 与 `sukkaw/mihomo/ip/china_ip.txt`
按其作者声明使用 **CC BY-SA 2.0**，不适用 AGPL-3.0。

SukkaW 在其 README 中**明确欢迎搭建镜像**并指定从 `SukkaLab/ruleset.skk.moe`
同步，本项目正是按此方式镜像。

### 使用前请注意

- **不提供任何担保。** 规则可能过时、误判或导致连接异常，风险自负。作者不对任何
  损失负责，包括但不限于网络不可用、服务被封禁、数据丢失。
- **商业代理服务的 ToS。** 部分服务商规定，使用第三方规则文件视为自动放弃 SLA
  与技术支持。使用前请先读你的服务条款。
- **规则数据不含任何绕过技术。** 本项目只是「哪些域名属于哪个服务」的分类数据，
  不主张也不指示任何流量该如何处理 —— 策略映射完全由你的配置决定。
- **遵守当地法律。** 你所在司法管辖区可能对网络流量转发有专门规定，使用者自行
  负责合规。

若任一上游作者认为本项目的镜像方式不妥，请提 issue，我会立即移除对应部分。
