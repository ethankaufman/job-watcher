"""Open today's GitHub Issue and close the previous day's, using the `gh` command.

In GitHub Actions `gh` is already logged in through the GH_TOKEN variable.
"""

import json
import subprocess

LABEL = "daily-report"


def gh(*args, check=True):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check).stdout


def publish_issue(title, body, run=gh):
    """Create the issue titled `title` (or update it, if a second run happens the same day)
    and close every other open daily-report issue. Returns the issue number."""
    run("label", "create", LABEL, "--color", "5319e7", "--description", "New and removed postings", "--force")
    open_issues = json.loads(run("issue", "list", "--label", LABEL, "--state", "open", "--limit", "100", "--json", "number,title"))

    today = next((i for i in open_issues if i["title"] == title), None)
    if today:
        run("issue", "edit", str(today["number"]), "--body", body)
        number = today["number"]
    else:
        url = run("issue", "create", "--title", title, "--body", body, "--label", LABEL).strip()
        number = int(url.rstrip("/").split("/")[-1])

    for issue in open_issues:
        if issue["number"] != number:
            run("issue", "close", str(issue["number"]), "--comment", f"Superseded by {title}.")
    return number
