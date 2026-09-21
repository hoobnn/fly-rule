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

`my-proxy.list` 会生成四个文件：

```text
custom/surge/my-proxy.conf           Surge RULE-SET，原样
custom/mihomo/my-proxy.yaml          behavior: classical，全部规则
custom/mihomo/my-proxy-domain.yaml   behavior: domain，仅域名
custom/mihomo/my-proxy-ip.yaml       behavior: ipcidr，仅 IP
```

域名类会按 mihomo 的写法转换：

| 源 | `-domain.yaml` |
| --- | --- |
| `DOMAIN,foo.example.org` | `foo.example.org` |
| `DOMAIN-SUFFIX,example.com` | `+.example.com` |
| `DOMAIN-KEYWORD,tracker` | `*tracker*` |

`PROCESS-NAME` 这类既不是域名也不是 IP，只出现在 Surge 与 classical 侧。

## 怎么引用

```ini
# Surge
RULE-SET,https://raw.githubusercontent.com/<user>/fly-rule/release/custom/surge/my-proxy.conf,🚀 代理
```

```yaml
# mihomo
rule-providers:
  # 通用，一份搞定
  my-proxy:
    type: http
    behavior: classical
    format: yaml
    interval: 86400
    url: https://raw.githubusercontent.com/<user>/fly-rule/release/custom/mihomo/my-proxy.yaml

  # 或者分开用，mihomo 只对 domain / ipcidr 这两种 behavior 做了优化，匹配更快
  my-proxy-domain:
    type: http
    behavior: domain
    format: yaml
    url: https://raw.githubusercontent.com/<user>/fly-rule/release/custom/mihomo/my-proxy-domain.yaml
  my-proxy-ip:
    type: http
    behavior: ipcidr
    format: yaml
    url: https://raw.githubusercontent.com/<user>/fly-rule/release/custom/mihomo/my-proxy-ip.yaml
```

`behavior` 必须与文件对应，写错 mihomo 会加载失败。

**顺序**：`-ip.yaml` 属于 IP 类规则，必须排在所有域名类规则之后，否则会在匹配时触发 DNS 解析。

## 为什么和同步产物分开

同步产物每次都从上游全量重建，任何手工改动都会被覆盖。自定义规则单独成目录，既不会被冲掉，也能一眼看出哪条是上游的、哪条是自己加的。

## 单独构建

```bash
python3 scripts/custom.py
```

只处理自定义规则，不拉上游，适合改完快速验证。
