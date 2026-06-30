<div align="right">

**简体中文** ｜ [English](README.en.md)

</div>

# uap_scraper — 抓取美国官方 UAP/UFO 公开资料

一个**纯标准库**（无需 `pip install`）的 Python 工具，用来从美国官方入口抓取 UAP/UFO 资料的元数据与文件：

- **PURSUE** — `https://www.war.gov/UFO/`
- **AARO 官方影像库** — `https://www.aaro.mil/UAP-Cases/Official-UAP-Imagery/`
- **NASA UAP** — `https://science.nasa.gov/uap/`
- **国家档案馆 RG 615** — `https://catalog.archives.gov/`（Catalog API v2）

> 要求：Python 3.9+（已在 3.11 测试）。无第三方依赖。

---

## ⚠️ 关于网络：本沙箱默认连不上这些官网

本远程容器启用了**网络出站白名单（egress allowlist）**。这些 `.gov / .mil / nasa.gov` 主机**不在白名单内**，代理会直接返回：

```
HTTP 403  x-deny-reason: host_not_allowed
Host not in allowlist: www.war.gov. Add this host to your network egress settings to allow access.
```

这**不是网站的问题，也不是代码的问题**，任何自定义 UA / 代理都无法绕过（也不应绕过）。两种解决办法：

1. **把目标主机加入环境的「网络出站」设置**，然后重跑。
   文档：https://code.claude.com/docs/en/claude-code-on-the-web
   需要放行的主机用 `doctor` 命令一键列出（见下）。
2. **在本地（普通联网的机器）运行本工具** —— 代码原样可用。

---

## 用法

所有命令都从仓库根目录运行，形式为 `python3 -m uap_scraper <子命令>`。

### 1) doctor —— 先检查哪些主机能连

```bash
python3 -m uap_scraper doctor          # 检查必需主机
python3 -m uap_scraper doctor --all    # 连可选 CDN 主机一起检查
```

输出会标出每个主机是 `OK` 还是 `BLOCKED`，并列出需要加入白名单的主机清单。

### 2) fetch —— 抓取元数据到 JSON

```bash
python3 -m uap_scraper fetch --source all --out data/uap_items.json
# 也可单独抓某个源：--source pursue|aaro|nasa|nara
```

把发现的视频/图片/音频/文档/档案记录写成结构化 JSON（含标题、链接、所在页面、描述等）。即使部分源被墙，也会写出已抓到的部分并提示被墙主机。

### 3) download —— 下载媒体文件

```bash
python3 -m uap_scraper download data/uap_items.json --kind video --out media
# --kind 可选 video,audio,image,document（逗号分隔）；--source 同上；--force 重下
```

按 `源/类型/文件名` 的目录结构保存（如 `media/pursue/video/xxx.mp4`）。

### 4) report —— 从 JSON 生成 Markdown 索引

```bash
python3 -m uap_scraper report data/uap_items.json --out docs/index.md
```

### 全局参数

- `--no-cache` 关闭磁盘缓存（默认缓存到 `.cache/`）
- `--delay 1.0` 请求间隔秒数（默认 1s，礼貌抓取）
- `-v` 详细日志

---

## NARA（国家档案馆）API key（可选）

RG 615 通过 NARA Catalog API v2 抓取。匿名亦可访问，但建议在 https://api.data.gov 申请免费 key，以提高配额：

```bash
export NARA_API_KEY=你的key
python3 -m uap_scraper fetch --source nara --out data/nara.json
```

---

## 测试

```bash
python3 -m unittest discover -s tests -v
```

离线单元测试覆盖了 HTML 媒体抽取、URL 分类、NARA JSON 解析等核心逻辑（不依赖网络）。

---

## 设计要点

- **egress 感知**：识别代理的 `host_not_allowed` 响应，抛出 `EgressBlocked` 并给出可操作指引，而不是丢一个看不懂的 403。
- **纯标准库**：`urllib` + `html.parser` + `json`，可在任何装了 Python 的机器上零依赖运行（沙箱里 `pip` 虽可用，但目标主机仍被墙，故不依赖第三方库）。
- **健壮抓取**：浏览器 UA、指数退避重试、gzip 处理、磁盘缓存、礼貌限速。
- **结构化输出**：统一的 `MediaItem` 模型，便于后续翻译/建库。

> 合规提示：本工具仅抓取**公开**的政府资料，请遵守各站 `robots.txt` 与使用条款，保持低频礼貌抓取。
