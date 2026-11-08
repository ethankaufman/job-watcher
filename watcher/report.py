"""Write the text of the daily GitHub Issue: the new and the removed postings, each with a link."""

MAX_SECTION = 28000  # characters. GitHub refuses an issue body over 65,536 characters in all


def new_postings(rows, day):
    """Postings first seen on `day`, leaving out the ones already open when watching began."""
    return [r for r in rows if r["first_seen"] == day and not r["first_run"]]


def removed_postings(rows, day):
    return [r for r in rows if r["removed_date"] == day]


def ordered(postings):
    """Postings in my role first, then by employer and title."""
    return sorted(postings, key=lambda r: (not r["in_role"], r["employer"], r["title"], r["posting_id"]))


def line(row):
    title = row["title"].replace("[", "(").replace("]", ")")
    where = f" · {row['location']}" if row["location"] else ""
    mark = "★ " if row["in_role"] else ""
    return f"- {mark}[{title}](<{row['url']}>) · {row['employer']}{where}"


def section(heading, postings, empty):
    lines = [f"## {heading} ({len(postings)})", ""]
    if not postings:
        return lines + [empty, ""]
    used = 0
    for count, row in enumerate(ordered(postings)):
        text = line(row)
        if used + len(text) > MAX_SECTION:
            lines += ["", f"…and {len(postings) - count} more (they are all in the history on the site)."]
            break
        lines.append(text)
        used += len(text) + 1
    return lines + [""]


def issue_body(day, rows, results):
    """Markdown for the issue titled with the date. Always has a body, even with no changes."""
    lines = [f"Run of **{day}** (UTC). ★ marks a posting in my role.", ""]
    failed = [r for r in results if not r["ok"]]
    if failed:
        lines += ["## Sources that failed today", ""]
        lines += [f"- `{r['name']}` ({r['employer']}): {r.get('error')}" for r in failed]
        lines += ["", "A failed source is left alone: nothing is marked removed because of it.", ""]

    first_run = sum(1 for r in rows if r["first_run"] and r["first_seen"] == day)
    if first_run:
        lines += [f"{first_run} postings were already open when watching started for some sources today; "
                  "they are not counted as new.", ""]
    lines += section("New postings", new_postings(rows, day), "No new postings today.")
    lines += section("Removed postings", removed_postings(rows, day), "No postings were removed today.")
    return "\n".join(lines)
