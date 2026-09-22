# 自定义规则

**一份源文件，自动派生出 Surge 与 mihomo 三种格式。** 不用手工维护多份。

**这里是源文件，改动提交到 `main`。** 发布到 `release` 的是派生产物，不要去 `release` 分支上改 —— 每次构建都会重建那个分支，改动会丢。

## 怎么写

在这个目录下建 `<名字>.list`，用 classical 语法，**域名与 IP 可以混写在同一个文件里**：

```ini
# custom/my-proxy.list
DOMAIN,foo.example.org
DOMAIN-SUFFIX,example.com
DOMAIN-KEYWORD,tracker
IP-CIDR,192.0.2.0/24
IP-CIDR6,2001:db8::/32
PROCESS-NAME,Transmission
```

支持的规则类型：

| 类别 | 类型 |
| --- | --- |
| 域名 | `DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-KEYWORD`、`DOMAIN-WILDCARD` |
| IP | `IP-CIDR`、`IP-CIDR6`、`IP-ASN` |
| 其他 | `PROCESS-NAME`、`DST-PORT`、`SRC-PORT`、`SRC-IP-CIDR` |

`#` 开头是注释。写错类型或域名值不合法，构建会失败并指出是哪一行。

## 派生出什么

`my-proxy.list` 会生成八个文件，**两端都自动拆出域名与 IP 两份**：

```text
custom/surge/my-proxy.conf           Surge RULE-SET，域名与 IP 混写
custom/surge/my-proxy-domain.conf    仅域名类
custom/surge/my-proxy-ip.conf        仅 IP 类
custom/mihomo/my-proxy.yaml          behavior: classical，全部规则
custom/mihomo/my-proxy-domain.yaml   behavior: domain，仅域名
custom/mihomo/my-proxy-domain.mrs    同上，预编译二进制（推荐）
custom/mihomo/my-proxy-ip.yaml       behavior: ipcidr，仅 IP
custom/mihomo/my-proxy-ip.mrs        同上，预编译二进制（推荐）
```

### mrs 是什么，为什么只有两份

`.mrs` 是 mihomo 的预编译二进制格式：域名编译成 trie、IP 编译成 CIDR 集合，
加载时不用逐行解析，文件也更小。**mihomo 侧推荐优先用 mrs。**

**mrs 只支持 `domain` 与 `ipcidr` 两种 behavior，不支持 `classical`** ——
classical 是「规则类型 + 值」的混合列表，可以包含 `PROCESS-NAME` 这类既非域名
也非 IP 的规则，没有对应的可编译结构（mihomo 对 classical 调用转换会直接
panic）。所以 `my-proxy.yaml` 没有 mrs 版本，这是格式本身的限制，不是漏做。

换句话说：**只要全部引用 mrs，配置里就自然不会用到 classical。**

拆分的理由两端不同：

- **mihomo**：`domain` / `ipcidr` 是官方优化过的 behavior，匹配比 `classical` 快。
- **Surge**：为了满足顺序与 `no-resolve` 两个约束。域名规则必须全部排在 IP 规则
  之前，且 IP 规则要带 `no-resolve`。混写文件只能整体引用一次，没法同时满足这
  两点 —— 拆开后 `-domain` 放域名段、`-ip` 放 IP 段并加 `no-resolve`。

只有域名、或只有 IP 的规则集，直接用混写的那份更省事（只会生成用得上的文件，
纯域名规则集不会产出空的 `-ip`）。

`PROCESS-NAME` 这类既不是域名也不是 IP，归入 `-domain`：它们不参与 IP 匹配，
放在域名段不会触发 DNS 解析。

域名类会按 mihomo 的写法转换：

| 源 | `-domain.yaml` / `-domain.mrs` |
| --- | --- |
| `DOMAIN,foo.example.org` | `foo.example.org` |
| `DOMAIN-SUFFIX,example.com` | `+.example.com` |
| `DOMAIN-WILDCARD,*.example.com` | `*.example.com` |
| `DOMAIN-KEYWORD,tracker` | **不生成**（见下） |

`PROCESS-NAME` 这类既不是域名也不是 IP，只出现在 Surge 与 classical 侧。

### DOMAIN-KEYWORD 在 mihomo 的 domain 侧不生效

mihomo 的 `domain` behavior 里 `*` 是**整标签**通配（`*.a.com`、`a.*` 可以），
**不做子串匹配**。所以关键字规则在 `domain` / mrs 下无法表达 —— 写成 `*tracker*`
的话 mihomo 只会打一行 warning 就跳过，整表继续加载，事后极难发现。

因此构建时会把这类规则**从 `-domain` 产物里排除**，并在文件头写明跳过了几条，
保证产物标称的规则数与 mihomo 实际加载的条数一致。它们在 **Surge 与 classical
产物里照常生效**，定位和 `PROCESS-NAME` 一样：Surge 与 classical 专属。

同理，部分标签通配（如 `foo*.a.com`）也表达不了，会被一并排除。

需要在 mihomo 上按关键字匹配时，只能引用 classical 的 `my-proxy.yaml`，或者把
关键字改写成具体的 `DOMAIN-SUFFIX`。

## 怎么引用

```ini
# Surge —— 域名与 IP 分开引用（推荐：满足顺序与 no-resolve 约束）
# 放在域名规则区
RULE-SET,https://raw.githubusercontent.com/<user>/fly-rule/release/custom/surge/my-proxy-domain.conf,🚀 代理
# 放在所有域名规则之后的 IP 规则区
RULE-SET,https://raw.githubusercontent.com/<user>/fly-rule/release/custom/surge/my-proxy-ip.conf,🚀 代理,no-resolve

# 或者用混写的那份（只有域名或只有 IP 时更省事）
RULE-SET,https://raw.githubusercontent.com/<user>/fly-rule/release/custom/surge/my-proxy.conf,🚀 代理
```

```yaml
# mihomo —— 推荐：mrs 预编译，加载快、文件小，且不涉及 classical
rule-providers:
  my-proxy-domain:
    type: http
    behavior: domain
    format: mrs
    interval: 86400
    url: https://raw.githubusercontent.com/<user>/fly-rule/release/custom/mihomo/my-proxy-domain.mrs
  my-proxy-ip:
    type: http
    behavior: ipcidr
    format: mrs
    interval: 86400
    url: https://raw.githubusercontent.com/<user>/fly-rule/release/custom/mihomo/my-proxy-ip.mrs
```

`format` 必须跟着文件后缀走：`.mrs` 配 `format: mrs`，`.yaml` 配 `format: yaml`。

```yaml
# 退路一：同样拆分，但用 yaml（想直接看内容时方便）
  my-proxy-domain:
    type: http
    behavior: domain
    format: yaml
    url: https://raw.githubusercontent.com/<user>/fly-rule/release/custom/mihomo/my-proxy-domain.yaml

# 退路二：classical 一份搞定，但没有 mrs，且只有它能覆盖
# DOMAIN-KEYWORD / PROCESS-NAME 这类规则
  my-proxy:
    type: http
    behavior: classical
    format: yaml
    url: https://raw.githubusercontent.com/<user>/fly-rule/release/custom/mihomo/my-proxy.yaml
```

`behavior` 必须与文件对应，写错 mihomo 会加载失败。

**顺序**：`-ip.yaml` / `-ip.conf` 属于 IP 类规则，必须排在所有域名类规则之后，否则会在匹配时触发 DNS 解析。Surge 侧还要在行尾加 `no-resolve`。

## 为什么和同步产物分开

同步产物每次都从上游全量重建，任何手工改动都会被覆盖。自定义规则单独成目录，既不会被冲掉，也能一眼看出哪条是上游的、哪条是自己加的。

## 单独构建

```bash
python3 scripts/custom.py    # 派生 Surge / mihomo 文本产物
python3 scripts/mrs.py       # 编译 mrs（需要 mihomo 在 PATH 上）
python3 scripts/verify.py --only-custom
```

只处理自定义规则，不拉上游，适合改完快速验证。

`mrs.py` 需要 `mihomo` 可执行文件在 `PATH` 上（mrs 只能由它生成）。本地没装时
会跳过并提示，`verify.py` 默认也不会因为缺 mrs 报错 —— CI 里加了 `--require`
与 `--require-mrs`，保证发布出去的产物一定齐全。
