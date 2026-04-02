# GitHub 每日热榜邮件推送机器人

一个基于 Python 的自动化脚本：每天抓取 GitHub Trending，精选 5 个项目并发送 HTML 邮件。

## 1) 功能说明

- 获取 GitHub 当日 Trending 项目（网页抓取方式）。
- 精选前 5 个热榜项目。
- 自动生成每个项目的简短介绍（名称/链接、核心功能、关注价值）。
- 通过 SMTP 发送格式化 HTML 邮件。
- 支持 GitHub Actions 每日定时执行。

## 2) 本地运行

### 环境准备

- Python 3.10+（推荐 3.11）
- 可用 SMTP 服务（例如 QQ 邮箱、163、Gmail 企业邮箱等）

### 安装与配置

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 SMTP 和收件人信息。

可用以下方式加载并运行（macOS/Linux 示例）：

```bash
set -a
source .env
set +a
python main.py
```

## 3) 环境变量说明

- `GITHUB_TRENDING_URL`：Trending 源地址（可选，默认 daily）。
- `REQUEST_TIMEOUT_SECONDS`：请求超时秒数（默认 20）。
- `GITHUB_TOKEN`：可选。用于 GitHub API 兜底时提高限流配额。
- `SMTP_HOST`：SMTP 服务器地址。
- `SMTP_PORT`：SMTP 端口（通常 587）。
- `SMTP_USER`：SMTP 登录账号（通常是邮箱地址）。
- `SMTP_PASSWORD`：SMTP 授权码/应用专用密码（不是邮箱登录密码）。
- `EMAIL_FROM`：发件人邮箱地址。
- `EMAIL_TO`：收件人列表，多个用英文逗号分隔。

## 4) GitHub Actions 自动化

已提供工作流文件：`.github/workflows/daily_push.yml`。

### 需要在仓库中配置的 Secrets

在 GitHub 仓库页面：`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

必填：

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`

可选：

- `GITHUB_TRENDING_URL`
- `REQUEST_TIMEOUT_SECONDS`
- `GITHUB_TOKEN`

> 如果不设置可选项，脚本会使用默认值。

## 5) SMTP 授权码获取提示

- 以 QQ 邮箱为例：邮箱设置里开启 SMTP 服务并申请“授权码”。
- 将该授权码填入 `SMTP_PASSWORD`（本地 `.env` 或 GitHub Secret）。
- 不要把授权码写入代码仓库。

