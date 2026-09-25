# fly-rule

聚合多个上游的分流规则到 `release` 分支，Surge 与 mihomo 都能直接引用。
MetaCubeX 不出 Surge 格式，由本项目转换。

## 上游

| 上游 | 协议 | 处理 |
| --- | --- | --- |
| [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) | GPL-3.0 | 转换 + 镜像 |
| [SukkaLab/ruleset.skk.moe](https://github.com/SukkaLab/ruleset.skk.moe) | AGPL-3.0 | 纯镜像 |
| [Aethersailor/Custom_OpenClash_Rules](https://github.com/Aethersailor/Custom_OpenClash_Rules) | CC-BY-SA-4.0 | 纯镜像 |

## 产物

都在 `release` 分支，路径是 `<上游>/<数据集>/<格式>/`：

```text
metacubex/geosite/{surge,mihomo,mihomo-classical}/   1892 类
metacubex/geoip/{surge,mihomo}/                       260 类
metacubex/geo-lite-geosite/, geo-lite-geoip/           35 类
sukkaw/{surge,mihomo}/{domainset,non_ip,ip}/
aethersailor/rule/
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

`verify.py` 逐文件核对转换产物条数与上游一致、镜像逐字节一致；
`guard.py` 与上次发布比对，类别消失或条数暴跌超 50% 就拦下发布。CI 里都是硬门禁。

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
