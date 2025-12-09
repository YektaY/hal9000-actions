#!/usr/bin/env python3
"""
Post a failure comment to the GitHub issue when Hal 9000 cannot solve the issue.
"""

import argparse
import json
import subprocess
from pathlib import Path


def format_failure_comment(attempts: int, last_error: str, username: str) -> str:
    """Format the failure message."""
    
    lines = []
    
    lines.append(f"## 🔴 Hal 9000")
    lines.append("")
    lines.append(f"> I'm sorry, @{username}. I'm afraid I can't do that.")
    lines.append("")
    lines.append(f"I wasn't able to solve this issue after {attempts} attempts.")
    lines.append("")
    lines.append("### Last Error")
    lines.append("")
    lines.append("<details>")
    lines.append("<summary>Test output from final attempt</summary>")
    lines.append("")
    lines.append("```")
    
    # Truncate if too long
    if len(last_error) > 3000:
        last_error = last_error[:3000] + "\n...[truncated]"
    
    lines.append(last_error)
    lines.append("```")
    lines.append("")
    lines.append("</details>")
    lines.append("")
    lines.append("### What to do next")
    lines.append("")
    lines.append("- Review the error output above to understand what's failing")
    lines.append("- Consider breaking down the issue into smaller tasks")
    lines.append("- Add more context or specific requirements to the issue description")
    lines.append("- Remove the `Hal 9000` label and re-add it to try again")
    lines.append("")
    
    return "\n".join(lines)


def post_comment(repo: str, issue_number: int, body: str) -> None:
    """Post a comment to a GitHub issue using gh CLI."""
    
    result = subprocess.run(
        ["gh", "issue", "comment", str(issue_number), "--repo", repo, "--body", body],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error posting comment: {result.stderr}")
        raise RuntimeError(f"Failed to post comment: {result.stderr}")
    
    print(f"Successfully posted failure comment to issue #{issue_number}")


def main():
    parser = argparse.ArgumentParser(description="Post failure comment to GitHub issue")
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--username", required=True, help="GitHub username who triggered the action")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    
    # Load the response data
    response_path = output_dir / "response.json"
    
    attempts = 3
    last_error = "Unknown error - no output captured"
    
    if response_path.exists():
        with open(response_path) as f:
            data = json.load(f)
            attempts = data.get("attempts", 3)
            last_error = data.get("last_test_output", last_error)
    
    # Format and post the comment
    comment_body = format_failure_comment(attempts, last_error, args.username)
    post_comment(args.repo, args.issue_number, comment_body)
    
    return 0


if __name__ == "__main__":
    exit(main())
