#!/usr/bin/env python3
"""Collect everything the profile cards need into assets/profile.json.

Sources
  - GitHub GraphQL: account stats (commits incl. private, stars, repos, followers)
    and per-repo stars / description / language for the repos in profile.config.json
  - optional feed (Mastodon RSS or any RSS/Atom feed) for the latest posts

Standard library only, so CI needs no extra dependencies.

    STATS_TOKEN=$(gh auth token) python3 scripts/fetch_profile_data.py
"""
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = json.load(open(os.path.join(ROOT, "profile.config.json")))
OUT = os.path.join(ROOT, "assets", "profile.json")

LOGIN = CONFIG["login"]
REPOS = [t["repo"] for t in CONFIG.get("targets", [])]
FEED = (CONFIG.get("feed") or {}).get("rss")
TOKEN = os.environ.get("STATS_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
UA = "profile-card-generator"


def gql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, method="POST")
    req.add_header("Authorization", f"bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(json.dumps(data["errors"], indent=2))
    return data["data"]


def fetch_stats():
    user = gql(
        """query($login:String!){ user(login:$login){
             createdAt followers{totalCount}
             repositories(privacy:PUBLIC, ownerAffiliations:OWNER, isFork:false){totalCount}
           }}""",
        {"login": LOGIN},
    )["user"]
    stars, cursor = 0, None
    while True:
        page = gql(
            """query($login:String!,$cursor:String){ user(login:$login){
                 repositories(first:100, ownerAffiliations:OWNER, after:$cursor){
                   nodes{stargazerCount} pageInfo{hasNextPage endCursor}}}}""",
            {"login": LOGIN, "cursor": cursor},
        )["user"]["repositories"]
        stars += sum(n["stargazerCount"] for n in page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    # Commit contributions, year by year (restrictedContributionsCount covers private repos
    # when the token belongs to the account owner).
    commits, this_year = 0, datetime.datetime.now(datetime.timezone.utc).year
    for year in range(int(user["createdAt"][:4]), this_year + 1):
        cc = gql(
            """query($login:String!,$from:DateTime!,$to:DateTime!){ user(login:$login){
                 contributionsCollection(from:$from,to:$to){
                   totalCommitContributions restrictedContributionsCount}}}""",
            {"login": LOGIN, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"},
        )["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
    return {
        "repos": user["repositories"]["totalCount"],
        "stars": stars,
        "commits": commits,
        "followers": user["followers"]["totalCount"],
        "since": user["createdAt"][:4],
    }


def fetch_repos():
    out = {}
    for name in REPOS:
        r = gql(
            """query($o:String!,$n:String!){ repository(owner:$o,name:$n){
                 stargazerCount description url primaryLanguage{name} isFork pushedAt
                 repositoryTopics(first:10){nodes{topic{name}}}}}""",
            {"o": LOGIN, "n": name},
        )["repository"]
        if not r:
            print(f"  ! repo not found: {name}", file=sys.stderr)
            continue
        out[name] = {
            "stars": r["stargazerCount"],
            "description": r["description"] or "",
            "url": r["url"],
            "language": (r["primaryLanguage"] or {}).get("name", ""),
            "fork": r["isFork"],
            "pushed": (r["pushedAt"] or "")[:10],
            "topics": [n["topic"]["name"] for n in r["repositoryTopics"]["nodes"]],
        }
    return out


def strip_html(s):
    s = re.sub(r"<br\s*/?>", " ", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'").strip()


def fetch_feed(limit=12):
    req = urllib.request.Request(FEED, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = root.iter("item") if root.findall(".//item") else root.iter("{http://www.w3.org/2005/Atom}entry")
    posts = []
    for item in items:
        def txt(*tags):
            for t in tags:
                v = item.findtext(t) or item.findtext(f"{{http://www.w3.org/2005/Atom}}{t}")
                if v:
                    return v
            return ""
        url = txt("link")
        if not url:
            el = item.find("{http://www.w3.org/2005/Atom}link")
            url = el.get("href") if el is not None else ""
        raw = txt("pubDate", "updated", "published")
        try:
            dt = datetime.datetime.strptime(raw[:25], "%a, %d %b %Y %H:%M:%S")
        except ValueError:
            try:
                dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                dt = datetime.datetime.now()
        title = strip_html(txt("title")) or strip_html(txt("description", "summary", "content"))
        if len(title) > 110:
            title = title[:108].rstrip() + "…"
        posts.append({"title": title, "url": url, "date": dt.strftime("%Y-%m-%d")})
        if len(posts) >= limit:
            break
    return posts


def main():
    if not TOKEN:
        sys.exit("no token in STATS_TOKEN / GH_TOKEN / GITHUB_TOKEN")
    previous = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            previous = json.load(f)
    data = {"stats": fetch_stats(), "repos": fetch_repos(), "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    if FEED:
        try:
            data["posts"] = fetch_feed()
        except Exception as e:  # feed down: keep yesterday's posts instead of failing the run
            print("feed fetch failed, keeping previous posts:", e, file=sys.stderr)
            data["posts"] = previous.get("posts", [])
    else:
        data["posts"] = []
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("wrote", OUT, "→", data["stats"])


if __name__ == "__main__":
    main()
