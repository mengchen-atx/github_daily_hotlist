import datetime as dt
import html
import json
import os
import re
import smtplib
import ssl
import sys
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi


DEFAULT_TRENDING_URL = "https://github.com/trending?since=daily"


@dataclass
class Repo:
    full_name: str
    url: str
    description: str
    language: str
    stars_today: str


def _clean_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                key, value = s.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key:
                    continue
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                os.environ.setdefault(key, value)
    except OSError as exc:
        print(f"[WARN] Failed to read .env: {exc}")


def _strip_wrapping_quotes(value: str) -> str:
    v = value.strip()
    while v and v[0] in {'"', "'"}:
        v = v[1:].lstrip()
    while v and v[-1] in {'"', "'"}:
        v = v[:-1].rstrip()
    return v


def fetch_trending_html(url: str, timeout: int) -> str:
    print(f"[INFO] Fetching trending page: {url}")
    request = Request(
        url=url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    )
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=timeout, context=ssl_context) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                raise ValueError(f"Unexpected content type: {content_type}")
            return response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"Failed to fetch trending data: {exc}") from exc


def fetch_repos_from_search_api(timeout: int, count: int) -> List[Repo]:
    since = (dt.datetime.utcnow() - dt.timedelta(days=14)).strftime("%Y-%m-%d")
    query = f"created:>{since}"
    params = urlencode(
        {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": max(count * 2, 20),
        }
    )
    url = f"https://api.github.com/search/repositories?{params}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-daily-hotlist-bot",
    }
    token = _strip_wrapping_quotes(os.getenv("GITHUB_TOKEN", ""))
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url=url, headers=headers)
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=timeout, context=ssl_context) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Fallback API failed: {exc}") from exc

    items = payload.get("items", [])
    repos: List[Repo] = []
    for item in items:
        full_name = item.get("full_name", "").strip()
        html_url = item.get("html_url", "").strip()
        if not full_name or not html_url:
            continue
        repos.append(
            Repo(
                full_name=full_name,
                url=html_url,
                description=(item.get("description") or "暂无描述。").strip(),
                language=(item.get("language") or "Unknown").strip(),
                stars_today=str(item.get("stargazers_count", "N/A")),
            )
        )

    if not repos:
        raise RuntimeError("Fallback API returned zero repositories.")
    return repos


def fetch_additional_trending_repos(timeout: int) -> List[Repo]:
    language_urls = [
        "https://github.com/trending/python?since=daily",
        "https://github.com/trending/typescript?since=daily",
        "https://github.com/trending/go?since=daily",
        "https://github.com/trending/rust?since=daily",
    ]
    repos: List[Repo] = []
    for url in language_urls:
        try:
            html_text = fetch_trending_html(url, timeout=timeout)
            repos.extend(parse_repos_from_trending(html_text))
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Additional trending fetch failed for {url}: {exc}")
    return repos


def parse_repos_from_trending(html_text: str) -> List[Repo]:
    blocks = re.findall(r'<article class="Box-row".*?</article>', html_text, re.S)
    repos: List[Repo] = []

    for block in blocks:
        href_match = re.search(r'<h2[^>]*>.*?<a[^>]*href="(/[^"]+)"', block, re.S)
        if not href_match:
            continue

        path = href_match.group(1).strip()
        full_name = path.strip("/").replace(" ", "")
        url = f"https://github.com{path}"

        desc_match = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
        desc = _clean_text(desc_match.group(1)) if desc_match else "暂无描述。"

        lang_match = re.search(
            r'itemprop="programmingLanguage"[^>]*>(.*?)</span>', block, re.S
        )
        language = _clean_text(lang_match.group(1)) if lang_match else "Unknown"

        stars_today_match = re.search(r"([\d,]+)\s+stars today", block, re.I)
        stars_today = stars_today_match.group(1) if stars_today_match else "N/A"

        repos.append(
            Repo(
                full_name=full_name,
                url=url,
                description=desc,
                language=language,
                stars_today=stars_today,
            )
        )

    if not repos:
        raise RuntimeError("No repositories parsed from trending page.")
    return repos


def select_top_repos(repos: List[Repo], count: int = 5) -> List[Repo]:
    selected = repos[:count]
    if len(selected) < count:
        raise RuntimeError(f"Only found {len(selected)} repos, fewer than {count}.")
    return selected


def infer_value(repo: Repo) -> str:
    text = f"{repo.description} {repo.language}".lower()
    rules = [
        (["agent", "ai", "llm", "gpt", "rag"], "适合关注 AI 应用落地与自动化效率提升。"),
        (["devops", "kubernetes", "docker", "infra"], "适合用于工程基础设施和运维自动化实践。"),
        (["security", "auth", "encryption"], "对安全加固、身份认证和风控场景有参考价值。"),
        (["cli", "tool", "productivity"], "可直接用于提升开发流程效率和团队协作体验。"),
        (["web", "frontend", "react", "vue"], "适用于现代 Web 产品开发与前端工程优化。"),
        (["data", "analytics", "pipeline"], "适用于数据处理、分析和可观测性建设。"),
    ]
    for keywords, summary in rules:
        if any(keyword in text for keyword in keywords):
            return summary
    return "项目近期热度高，值得作为技术趋势和实现思路参考。"


def infer_core_function(repo: Repo) -> str:
    text = f"{repo.description} {repo.language}".lower()
    rules = [
        (["agent", "ai", "llm", "gpt", "rag"], "围绕 AI/大模型能力，提供模型调用、智能体编排或推理增强相关能力。"),
        (["devops", "kubernetes", "docker", "infra"], "提供部署、运维、容器编排或工程基础设施相关工具能力。"),
        (["security", "auth", "encryption"], "聚焦身份认证、权限控制、加密或安全防护能力建设。"),
        (["cli", "tool", "productivity"], "提供命令行或开发效率工具，帮助自动化日常研发流程。"),
        (["web", "frontend", "react", "vue"], "面向 Web 应用开发，增强前端工程化与交互构建效率。"),
        (["data", "analytics", "pipeline"], "面向数据采集、处理、分析或数据流水线建设。"),
    ]
    for keywords, summary in rules:
        if any(keyword in text for keyword in keywords):
            return summary
    return f"提供开源能力模块，核心关注点是：{repo.description or '提升开发效率与可维护性'}。"


def infer_use_case(repo: Repo) -> str:
    text = f"{repo.description} {repo.language}".lower()
    rules = [
        (["agent", "ai", "llm", "gpt", "rag"], "适用于 AI 应用开发、自动化助手、企业知识问答等场景。"),
        (["devops", "kubernetes", "docker", "infra"], "适用于服务部署、环境管理、持续交付与平台工程场景。"),
        (["security", "auth", "encryption"], "适用于账号体系、安全审计、数据保护与合规场景。"),
        (["cli", "tool", "productivity"], "适用于个人开发提效、团队工程规范落地与脚本自动化场景。"),
        (["web", "frontend", "react", "vue"], "适用于中后台、SaaS 产品与 Web 交互应用开发场景。"),
        (["data", "analytics", "pipeline"], "适用于数据平台建设、业务分析和指标监控场景。"),
    ]
    for keywords, summary in rules:
        if any(keyword in text for keyword in keywords):
            return summary
    return "适用于学习优秀工程实现思路，并按需集成到实际项目。"


def build_html_email(repos: List[Repo]) -> str:
    today = dt.datetime.now().strftime("%Y-%m-%d")
    cards = []
    for idx, repo in enumerate(repos, start=1):
        card = f"""
        <div style="padding:14px 16px; margin:10px 0; border:1px solid #e5e7eb; border-radius:10px;">
          <h3 style="margin:0 0 8px 0; font-size:16px;">
            {idx}. <a href="{repo.url}" style="text-decoration:none; color:#0969da;">{repo.full_name}</a>
          </h3>
          <p style="margin:6px 0; color:#374151;"><strong>核心功能：</strong>{html.escape(infer_core_function(repo))}</p>
          <p style="margin:6px 0; color:#374151;"><strong>是干什么的：</strong>{html.escape(infer_use_case(repo))}</p>
          <p style="margin:6px 0; color:#374151;"><strong>值得关注：</strong>{html.escape(infer_value(repo))}</p>
          <p style="margin:6px 0; color:#6b7280; font-size:13px;">项目简介：{html.escape(repo.description)}</p>
          <p style="margin:6px 0; color:#6b7280; font-size:13px;">语言：{html.escape(repo.language)} | 今日新增 Star：{html.escape(repo.stars_today)}</p>
        </div>
        """
        cards.append(card)

    return f"""
    <html>
      <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif; background:#f9fafb; margin:0; padding:24px;">
        <div style="max-width:760px; margin:0 auto; background:#ffffff; border-radius:12px; border:1px solid #e5e7eb; padding:20px;">
          <h2 style="margin:0 0 10px 0;">GitHub 每日热榜精选（{today}）</h2>
          <p style="color:#4b5563; margin:0 0 16px 0;">今日精选 5 个值得关注的开源项目，帮助你快速掌握技术趋势。</p>
          {''.join(cards)}
          <hr style="border:none; border-top:1px solid #e5e7eb; margin:16px 0;" />
          <p style="font-size:12px; color:#6b7280; margin:0;">由 GitHub Trending 自动生成并发送。</p>
        </div>
      </body>
    </html>
    """


def send_email(subject: str, html_body: str) -> None:
    smtp_host = _strip_wrapping_quotes(os.getenv("SMTP_HOST", ""))
    smtp_port_raw = _strip_wrapping_quotes(os.getenv("SMTP_PORT", "587"))
    try:
        smtp_port = int(smtp_port_raw or "587")
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT must be an integer.") from exc
    smtp_user = _strip_wrapping_quotes(os.getenv("SMTP_USER", ""))
    smtp_password = _strip_wrapping_quotes(os.getenv("SMTP_PASSWORD", ""))
    email_from = _strip_wrapping_quotes(os.getenv("EMAIL_FROM", ""))
    email_to = _strip_wrapping_quotes(os.getenv("EMAIL_TO", ""))

    missing = [
        name
        for name, value in {
            "SMTP_HOST": smtp_host,
            "SMTP_USER": smtp_user,
            "SMTP_PASSWORD": smtp_password,
            "EMAIL_FROM": email_from,
            "EMAIL_TO": email_to,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    recipients = []
    for addr in email_to.split(","):
        cleaned = _strip_wrapping_quotes(addr).replace(" ", "")
        if cleaned:
            recipients.append(cleaned)
    if not recipients:
        raise RuntimeError("EMAIL_TO is empty after parsing.")

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = email_from
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(html_body, "html", "utf-8"))

    print(f"[INFO] Sending email via SMTP {smtp_host}:{smtp_port} to {recipients}")
    try:
        # Gmail app passwords are commonly shown with spaces; SMTP login needs raw token.
        if "gmail.com" in smtp_host.lower():
            smtp_password = smtp_password.replace(" ", "")
        context = ssl.create_default_context(cafile=certifi.where())
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(email_from, recipients, message.as_string())
    except (smtplib.SMTPException, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Failed to send email: {exc}") from exc


def main() -> int:
    load_dotenv()
    timeout_raw = _strip_wrapping_quotes(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
    trending_url = (
        _strip_wrapping_quotes(os.getenv("GITHUB_TRENDING_URL", ""))
        or DEFAULT_TRENDING_URL
    )

    try:
        timeout = int(timeout_raw or "20")
    except ValueError:
        raise SystemExit("[ERROR] REQUEST_TIMEOUT_SECONDS must be an integer.")

    try:
        html_text = fetch_trending_html(trending_url, timeout=timeout)
        repos = parse_repos_from_trending(html_text)
        if len(repos) < 5:
            print(
                f"[WARN] Trending parser returned {len(repos)} repos, trying additional trending pages."
            )
            fallback_repos = fetch_additional_trending_repos(timeout=timeout)
            existing = {repo.full_name for repo in repos}
            for repo in fallback_repos:
                if repo.full_name in existing:
                    continue
                repos.append(repo)
                existing.add(repo.full_name)
                if len(repos) >= 5:
                    break
        if len(repos) < 5:
            print(
                f"[WARN] Still {len(repos)} repos after extra trending pages, trying GitHub Search API."
            )
            fallback_repos = fetch_repos_from_search_api(timeout=timeout, count=5)
            existing = {repo.full_name for repo in repos}
            for repo in fallback_repos:
                if repo.full_name in existing:
                    continue
                repos.append(repo)
                existing.add(repo.full_name)
                if len(repos) >= 5:
                    break
        selected = select_top_repos(repos, count=5)
        email_html = build_html_email(selected)
        subject = f"GitHub 每日热榜精选 - {dt.datetime.now().strftime('%Y-%m-%d')}"
        send_email(subject, email_html)
        print("[INFO] Done. Daily hotlist email sent successfully.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

