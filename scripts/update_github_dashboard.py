import datetime as dt
import html
import json
import os
import urllib.request

USERNAME = os.environ.get("GITHUB_USERNAME", "akhileshreddy11")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = "assets/github-dashboard.svg"


def request_json(url, method="GET", body=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "akhileshreddy11-profile-dashboard",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())


def graphql(query, variables):
    return request_json(
        "https://api.github.com/graphql",
        "POST",
        {"query": query, "variables": variables},
    )


def esc(value):
    return html.escape(str(value), quote=True)


def text(x, y, value, size=16, fill="#f4f7ff", weight="400", anchor="start"):
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" '
        f'font-family="Inter,Arial,Helvetica,sans-serif" font-size="{size}px" '
        f'font-weight="{weight}" text-anchor="{anchor}">{esc(value)}</text>'
    )


def rect(x, y, w, h, fill="#0d1428", stroke="#25365d", r=16):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
    )


def main():
    today = dt.date.today()
    from_date = today - dt.timedelta(days=365)
    refreshed = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Live profile data.
    profile = request_json(f"https://api.github.com/users/{USERNAME}")
    repos = []
    page = 1
    while True:
        batch = request_json(
            f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner"
        )
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    # Contribution calendar from GitHub GraphQL.
    query = """
    query($login:String!, $from:DateTime!, $to:DateTime!) {
      user(login:$login) {
        contributionsCollection(from:$from, to:$to) {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    data = graphql(query, {
        "login": USERNAME,
        "from": f"{from_date.isoformat()}T00:00:00Z",
        "to": f"{today.isoformat()}T23:59:59Z",
    })
    if data.get("errors"):
        raise RuntimeError(data["errors"])

    calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [d for week in calendar["weeks"] for d in week["contributionDays"]]
    counts = {d["date"]: int(d["contributionCount"]) for d in days}
    total = int(calendar["totalContributions"])

    current_streak = 0
    cursor = today
    while counts.get(cursor.isoformat(), 0) > 0:
        current_streak += 1
        cursor -= dt.timedelta(days=1)

    longest_streak = 0
    run = 0
    for day in sorted(days, key=lambda item: item["date"]):
        if int(day["contributionCount"]) > 0:
            run += 1
            longest_streak = max(longest_streak, run)
        else:
            run = 0

    # Repository statistics and language mix.
    owned_repos = [repo for repo in repos if not repo.get("fork")]
    stars = sum(int(repo.get("stargazers_count", 0)) for repo in owned_repos)
    language_bytes = {}
    for repo in owned_repos:
        try:
            languages = request_json(repo["languages_url"])
            for language, amount in languages.items():
                language_bytes[language] = language_bytes.get(language, 0) + int(amount)
        except Exception:
            pass
    top_languages = sorted(language_bytes.items(), key=lambda item: item[1], reverse=True)[:6]
    language_total = sum(language_bytes.values()) or 1

    # Recent public GitHub activity. This is intentionally live rather than hard-coded.
    try:
        events = request_json(f"https://api.github.com/users/{USERNAME}/events/public?per_page=30")
    except Exception:
        events = []

    def event_label(event):
        event_type = event.get("type", "Activity").replace("Event", "")
        mapping = {
            "Push": "Pushed code",
            "PullRequest": "Pull request activity",
            "Issues": "Issue activity",
            "Create": "Created something",
            "Delete": "Deleted something",
            "Release": "Published a release",
            "Fork": "Forked a repository",
            "Watch": "Starred a repository",
        }
        return mapping.get(event_type, event_type)

    recent_activity = []
    for event in events:
        repo_name = event.get("repo", {}).get("name", "GitHub")
        created = event.get("created_at", "")
        when = created[:10] if created else "Recent"
        recent_activity.append((event_label(event), repo_name.split("/", 1)[-1], when))
        if len(recent_activity) == 5:
            break

    last_event = events[0].get("created_at", "") if events else ""
    last_activity = last_event.replace("T", " ").replace("Z", " UTC") if last_event else "No recent public event"

    # SVG canvas.
    W, H = 1200, 900
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    out.append("""
    <defs>
      <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#070a14"/>
        <stop offset="0.55" stop-color="#0d1222"/>
        <stop offset="1" stop-color="#11172a"/>
      </linearGradient>
      <linearGradient id="line" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#6d5dfc"/>
        <stop offset="1" stop-color="#2bd7ff"/>
      </linearGradient>
      <linearGradient id="live" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#2de28a"/>
        <stop offset="1" stop-color="#25c8ff"/>
      </linearGradient>
    </defs>
    """)
    out.append('<rect width="1200" height="900" rx="26" fill="url(#bg)" stroke="#2b3b63"/>')

    # Header.
    out.append(text(44, 52, "GITHUB // LIVE ACTIVITY", 13, "#7585ad", "700"))
    out.append(text(44, 88, f"{USERNAME}", 31, "#ffffff", "700"))
    out.append(text(44, 116, "Real GitHub data • automatically refreshed by GitHub Actions", 14, "#9aa8ca"))
    out.append('<circle cx="1090" cy="76" r="6" fill="#32e68b"/>')
    out.append(text(1106, 81, "LIVE DATA", 12, "#6ff0a7", "700"))
    out.append(text(1156, 112, f"Updated {refreshed}", 10, "#66779e", "400", "end"))

    # Primary live metrics.
    metrics = [
        ("CONTRIBUTIONS", total, "12 months", "#2de28a"),
        ("STREAK", current_streak, "current days", "#2bd7ff"),
        ("BEST STREAK", longest_streak, "days", "#ffc857"),
        ("REPOSITORIES", profile.get("public_repos", len(owned_repos)), "public", "#a980ff"),
        ("STARS", stars, "all owned repos", "#ff78b7"),
        ("FOLLOWERS", profile.get("followers", 0), "current", "#62a7ff"),
    ]
    for i, (label, value, sub, accent) in enumerate(metrics):
        col = i % 3
        row = i // 3
        x = 44 + col * 376
        y = 145 + row * 112
        out.append(rect(x, y, 350, 94, "#0a1020", accent, 15))
        out.append(text(x + 18, y + 27, label, 11, "#7f8caf", "700"))
        out.append(text(x + 18, y + 65, value, 28, accent, "700"))
        out.append(text(x + 326, y + 64, sub, 11, "#9ba8c7", "400", "end"))

    # Contribution heatmap.
    out.append(rect(44, 390, 620, 270))
    out.append(text(64, 422, "Contribution Heatmap", 18, "#ffffff", "700"))
    out.append(text(64, 445, "Daily contribution count from the GitHub calendar", 11, "#7f8caf"))

    recent_days = sorted(days, key=lambda item: item["date"])[-182:]
    recent_map = {item["date"]: int(item["contributionCount"]) for item in recent_days}
    max_count = max([int(item["contributionCount"]) for item in recent_days] + [1])
    start = today - dt.timedelta(days=181)
    start_x, start_y, cell, gap = 68, 472, 14, 3
    shades = ["#17213a", "#214f45", "#1d8a63", "#20c878", "#38e991"]
    for i in range(182):
        day = start + dt.timedelta(days=i)
        value = recent_map.get(day.isoformat(), 0)
        col = i // 7
        row = i % 7
        if value == 0:
            fill = shades[0]
        elif value >= max_count * 0.75:
            fill = shades[4]
        elif value >= max_count * 0.45:
            fill = shades[3]
        elif value >= max_count * 0.2:
            fill = shades[2]
        else:
            fill = shades[1]
        out.append(
            f'<rect x="{start_x + col*(cell+gap)}" y="{start_y + row*(cell+gap)}" '
            f'width="{cell}" height="{cell}" rx="3" fill="{fill}"/>'
        )
    out.append(text(68, 615, "LESS", 9, "#68799e", "700"))
    for i, fill in enumerate(shades):
        out.append(f'<rect x="104" y="605" width="14" height="14" rx="3" fill="{fill}"/>')
    out.append(text(222, 615, "MORE", 9, "#68799e", "700"))

    # Language mix.
    out.append(rect(682, 390, 474, 270))
    out.append(text(704, 422, "Language Mix", 18, "#ffffff", "700"))
    out.append(text(704, 445, "Calculated from language bytes in your repositories", 11, "#7f8caf"))
    language_accents = ["#3aa7ff", "#ffd34e", "#ff745d", "#a57cff", "#41d39a", "#8b98b8"]
    for i, (language, amount) in enumerate(top_languages):
        pct = amount / language_total * 100
        y = 480 + i * 27
        accent = language_accents[i]
        out.append(f'<circle cx="710" cy="{y-4}" r="5" fill="{accent}"/>')
        out.append(text(724, y, language, 12, "#e7ebf7", "700"))
        out.append(f'<rect x="820" y="{y-11}" width="245" height="8" rx="4" fill="#1c2741"/>')
        out.append(f'<rect x="820" y="{y-11}" width="{245*pct/100:.1f}" height="8" rx="4" fill="{accent}"/>')
        out.append(text(1132, y, f"{pct:.1f}%", 10, "#98a7c8", "700", "end"))

    # Live activity and trend.
    out.append(rect(44, 684, 1112, 172))
    out.append(text(64, 716, "Recent GitHub Activity", 18, "#ffffff", "700"))
    out.append('<circle cx="252" cy="710" r="5" fill="#31e58b"/>')
    out.append(text(265, 714, "PUBLIC EVENT STREAM", 10, "#65e9a0", "700"))
    out.append(text(1134, 714, f"Last event: {last_activity}", 10, "#66779e", "400", "end"))

    if recent_activity:
        for i, (label, repo, when) in enumerate(recent_activity):
            x = 64 + i * 218
            out.append(rect(x, 742, 202, 88, "#0b1223", "#223352", 12))
            out.append(text(x + 13, 765, label, 11, "#dfe6f7", "700"))
            out.append(text(x + 13, 786, repo[:25], 11, "#6fcfff"))
            out.append(text(x + 13, 807, when, 10, "#7181a4"))
    else:
        out.append(text(64, 780, "No recent public events returned by GitHub.", 12, "#8d9abb"))

    out.append(text(600, 880, "No hard-coded activity numbers • values are regenerated from GitHub APIs", 10, "#5f6f94", "400", "middle"))
    out.append('</svg>')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as file:
        file.write("\n".join(out))


if __name__ == "__main__":
    main()
