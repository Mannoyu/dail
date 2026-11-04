from datetime import datetime
from urllib.parse import quote

from collector.common import check_window, guarded, parse_time
from shared.config import get_config, secret
from shared.errors import CollectorError
from shared.http import APIClient
from shared.models import CommitRecord


def _pages(api, url, headers, params=None):
    page = 1
    while True:
        batch = api.request(
            "GET",
            url,
            headers=headers,
            params={**(params or {}), "per_page": 100, "page": page},
        )
        if not isinstance(batch, list):
            raise CollectorError("GitHub 列表格式错误")
        yield from batch
        if len(batch) < 100:
            return
        page += 1


@guarded
def collect(repos: list[str], since: datetime, until: datetime) -> list[CommitRecord]:
    check_window(since, until)
    cfg = get_config().github
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {secret(cfg.token_env)}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    records: list[CommitRecord] = []
    seen: set[tuple[str, str]] = set()
    with APIClient() as api:
        for repo in dict.fromkeys(repos):
            if repo not in cfg.repos:
                raise CollectorError("仓库不在配置白名单内")
            base = "https://api.github.com/repos/" + quote(repo, safe="/")
            for branch in _pages(api, base + "/branches", headers):
                for item in _pages(
                    api,
                    base + "/commits",
                    headers,
                    {
                        "sha": branch["commit"]["sha"],
                        "since": since.isoformat(),
                        "until": until.isoformat(),
                    },
                ):
                    sha = item["sha"]
                    if (repo, sha) in seen:
                        continue
                    seen.add((repo, sha))
                    detail = api.request(
                        "GET",
                        base + "/commits/" + quote(sha, safe=""),
                        headers=headers,
                        params={"per_page": 100},
                    )
                    commit = detail["commit"]
                    timestamp = parse_time(commit["committer"]["date"])
                    if not since <= timestamp <= until:
                        continue
                    author = (detail.get("author") or {}).get("login")
                    # Unlinked Git identities must not be silently attributed by display name.
                    author = author or commit["author"].get("email", "unmapped")
                    # GitHub paginates files separately; stats are global, files count needs all pages.
                    files = len(detail.get("files", []))
                    stats = detail["stats"]
                    file_page = 2
                    while len(detail.get("files", [])) == 100:
                        if files >= 3000:
                            raise CollectorError("提交文件数量达到 GitHub 枚举上限")
                        detail = api.request(
                            "GET",
                            base + "/commits/" + quote(sha, safe=""),
                            headers=headers,
                            params={"per_page": 100, "page": file_page},
                        )
                        files += len(detail.get("files", []))
                        file_page += 1
                    records.append(
                        CommitRecord(
                            author=author,
                            message=commit["message"],
                            timestamp=timestamp,
                            repo=repo,
                            additions=int(stats["additions"]),
                            deletions=int(stats["deletions"]),
                            files_changed=files,
                        )
                    )
    return sorted(records, key=lambda record: record.timestamp)
