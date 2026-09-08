import datetime as dt
import html
import json
import os
import urllib.request

USERNAME = os.environ.get("GITHUB_USERNAME", "akhileshreddy11")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = "assets/github-dashboard.svg"


def request_json(url, method="GET", body=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-dashboard"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def graphql(query, variables):
    return request_json("https://api.github.com/graphql", "POST", {"query": query, "variables": variables})


def esc(value):
    return html.escape(str(value), quote=True)


def svg_text(x, y, text, size=16, fill="#f5f7ff", weight="400", anchor="start"):
    return f'<text x="{x}" y="{y}" fill="{fill}" font-family="Arial,Helvetica,sans-serif" font-size="{size}px" font-weight="{weight}" text-anchor="{anchor}">{esc(text)}</text>'


def round_rect(x, y, w, h, fill="#0d1428", stroke="#26365e", r=14):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"/>'


def main():
    today = dt.date.today()
    from_date = today - dt.timedelta(days=365)
    query = """
    query($login:String!, $from:DateTime!, $to:DateTime!) {
      user(login:$login) {
        contributionsCollection(from:$from, to:$to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { date contributionCount }
            }
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
    days = [d for w in calendar["weeks"] for d in w["contributionDays"]]
    counts = {d["date"]: int(d["contributionCount"]) for d in days}
    total = int(calendar["totalContributions"])

    current = 0
    cursor = today
    while counts.get(cursor.isoformat(), 0) > 0:
        current += 1
        cursor -= dt.timedelta(days=1)

    longest = 0
    run = 0
    for d in sorted(days, key=lambda x: x["date"]):
        if int(d["contributionCount"]) > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    repos = []
    for page in (1, 2):
        batch = request_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner")
        repos.extend(batch)
        if len(batch) < 100:
            break

    stars = sum(int(r.get("stargazers_count", 0)) for r in repos)
    language_bytes = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        try:
            langs = request_json(repo["languages_url"])
            for lang, amount in langs.items():
                language_bytes[lang] = language_bytes.get(lang, 0) + int(amount)
        except Exception:
            continue

    top_langs = sorted(language_bytes.items(), key=lambda x: x[1], reverse=True)[:5]
    lang_total = sum(language_bytes.values()) or 1

    # Last 26 weeks for a compact activity heatmap.
    recent_days = sorted(days, key=lambda x: x["date"])[-182:]
    max_count = max([int(d["contributionCount"]) for d in recent_days] + [1])

    W, H = 1200, 820
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    out.append('<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#080b18"/><stop offset="1" stop-color="#11162a"/></linearGradient><linearGradient id="accent" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#6c5ce7"/><stop offset="1" stop-color="#25c8ff"/></linearGradient></defs>')
    out.append('<rect width="1200" height="820" rx="22" fill="url(#bg)" stroke="#34456f"/>')
    out.append(svg_text(42, 58, "📊 GitHub Dashboard", 30, "#ffffff", "700"))
    out.append(svg_text(42, 88, "Live profile metrics generated automatically from GitHub.", 15, "#aeb9d9"))

    cards = [
        ("TOTAL CONTRIBUTIONS", total, "Last 12 months", "#36d399"),
        ("CURRENT STREAK", current, "Consecutive days", "#22c7ff"),
        ("LONGEST STREAK", longest, "Best run", "#f4c542"),
        ("REPOSITORY STARS", stars, "Across public repos", "#a77bff"),
    ]
    for i, (label, value, sub, accent) in enumerate(cards):
        x = 42 + i * 282
        out.append(round_rect(x, 115, 260, 105, "#0b1325", accent))
        out.append(svg_text(x + 18, 145, label, 12, "#8f9abb", "700"))
        out.append(svg_text(x + 18, 184, value, 30, accent, "700"))
        out.append(svg_text(x + 18, 207, sub, 12, "#b9c4e2"))

    # Contribution heatmap
    out.append(round_rect(42, 245, 520, 300))
    out.append(svg_text(62, 278, "Contribution Activity", 19, "#ffffff", "700"))
    start_x, start_y, cell, gap = 66, 310, 12, 3
    recent_map = {d["date"]: int(d["contributionCount"]) for d in recent_days}
    start = today - dt.timedelta(days=181)
    for i in range(182):
        day = start + dt.timedelta(days=i)
        col = i // 7
        row = i % 7
        c = recent_map.get(day.isoformat(), 0)
        if c == 0:
            fill = "#17223b"
        elif c >= max_count * 0.75:
            fill = "#35e68f"
        elif c >= max_count * 0.45:
            fill = "#20c878"
        elif c >= max_count * 0.2:
            fill = "#168b62"
        else:
            fill = "#245541"
        out.append(f'<rect x="{start_x + col*(cell+gap)}" y="{start_y + row*(cell+gap)}" width="{cell}" height="{cell}" rx="3" fill="{fill}"/>')
    out.append(svg_text(66, 442, "Less", 11, "#8490b0"))
    for j, c in enumerate(["#17223b", "#245541", "#168b62", "#20c878", "#35e68f"]):
        out.append(f'<rect x="{102+j*20}" y="432" width="14" height="14" rx="3" fill="{c}"/>')
    out.append(svg_text(212, 442, "More", 11, "#8490b0"))

    # Top languages
    out.append(round_rect(582, 245, 270, 300))
    out.append(svg_text(602, 278, "Top Languages", 19, "#ffffff", "700"))
    lang_accents = ["#36a2ff", "#ffd84d", "#ff7655", "#9b6cff", "#8e9bb9"]
    for i, (lang, amount) in enumerate(top_langs):
        pct = amount / lang_total * 100
        y = 320 + i * 42
        out.append(f'<circle cx="608" cy="{y-5}" r="7" fill="{lang_accents[i]}"/>')
        out.append(svg_text(625, y, lang, 13, "#e5eaff", "700"))
        out.append(f'<rect x="705" y="{y-13}" width="115" height="10" rx="5" fill="#202b46"/>')
        out.append(f'<rect x="705" y="{y-13}" width="{115*pct/100:.1f}" height="10" rx="5" fill="{lang_accents[i]}"/>')
        out.append(svg_text(832, y, f"{pct:.1f}%", 11, "#9eabd0", "700", "end"))

    # Recent activity line graph
    out.append(round_rect(872, 245, 286, 300))
    out.append(svg_text(892, 278, "Activity Graph", 19, "#ffffff", "700"))
    graph_days = recent_days[-84:]
    values = [int(d["contributionCount"]) for d in graph_days]
    vmax = max(values + [1])
    points = []
    gx, gy, gw, gh = 895, 330, 240, 135
    for i, val in enumerate(values):
        x = gx + i * gw / max(1, len(values)-1)
        y = gy + gh - (val / vmax) * gh
        points.append(f"{x:.1f},{y:.1f}")
    out.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="url(#accent)" stroke-width="3"/>')
    out.append(f'<line x1="{gx}" y1="{gy+gh}" x2="{gx+gw}" y2="{gy+gh}" stroke="#263454"/>')
    out.append(svg_text(895, 485, "Last 12 weeks", 11, "#8793b4"))
    out.append(svg_text(1135, 485, f"{sum(values)} contributions", 11, "#7fdcff", "700", "end"))

    out.append(round_rect(42, 575, 1116, 190, "#0a1122", "#27375f"))
    out.append(svg_text(62, 610, "Profile Focus", 19, "#ffffff", "700"))
    focus = [
        ("AI Engineering", "Agentic AI • RAG • MLOps"),
        ("Featured Build", "CreatorOS"),
        ("Computer Vision", "FindBuddy"),
        ("Platform", "OmniMind"),
    ]
    for i, (title, sub) in enumerate(focus):
        x = 62 + i*270
        out.append(round_rect(x, 635, 250, 85, "#111a30", "#263a67"))
        out.append(svg_text(x+16, 665, title, 14, "#ffffff", "700"))
        out.append(svg_text(x+16, 692, sub, 12, "#9eabd0"))
    out.append(svg_text(600, 750, "Updated automatically by GitHub Actions • Open source today. Build better tomorrow.", 12, "#7180a6", "400", "middle"))
    out.append('</svg>')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


if __name__ == "__main__":
    main()
