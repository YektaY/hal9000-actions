#!/usr/bin/env python3
"""
Post a formatted diff comment to the GitHub issue.
Creates collapsible sections for each file with syntax highlighting.
"""

import argparse
import json
import subprocess
from pathlib import Path
from difflib import unified_diff


def generate_unified_diff(old_content: str, new_content: str, filename: str) -> str:
    """Generate a unified diff between old and new content."""
    
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    diff = unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm=""
    )
    
    return "".join(diff)


def get_language_for_file(filename: str) -> str:
    """Get the syntax highlighting language for a file."""
    
    ext_to_lang = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "jsx",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".java": "java",
        ".kt": "kotlin",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".xml": "xml",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".sql": "sql",
        ".sh": "bash",
        ".md": "markdown",
        ".rs": "rust",
        ".go": "go",
        ".rb": "ruby",
        ".php": "php",
    }
    
    ext = Path(filename).suffix.lower()
    return ext_to_lang.get(ext, "")


def format_diff_comment(changes: list[dict], explanation: str) -> str:
    """Format the changes as a GitHub markdown comment with collapsible sections."""
    
    lines = []
    
    # Header
    lines.append("## 🤖 Hal 9000 - Proposed Changes")
    lines.append("")
    
    # Explanation
    if explanation:
        lines.append("### Explanation")
        lines.append("")
        lines.append(explanation)
        lines.append("")
    
    # File changes
    lines.append("### Changed Files")
    lines.append("")
    
    for change in changes:
        path = change["path"]
        action = change.get("action", "modify")
        old_content = change.get("old", "")
        new_content = change.get("new", "")
        
        # Action emoji
        action_emoji = {
            "create": "✨",
            "modify": "✏️",
            "delete": "🗑️"
        }.get(action, "📄")
        
        # Get language for syntax highlighting
        lang = get_language_for_file(path)
        
        # Create collapsible section
        lines.append(f"<details>")
        lines.append(f"<summary>{action_emoji} <code>{path}</code> ({action})</summary>")
        lines.append("")
        
        if action == "delete":
            lines.append("```diff")
            for line in old_content.splitlines():
                lines.append(f"- {line}")
            lines.append("```")
        
        elif action == "create":
            lines.append(f"```{lang}")
            lines.append(new_content)
            lines.append("```")
        
        else:  # modify
            diff = generate_unified_diff(old_content, new_content, path)
            if diff:
                lines.append("```diff")
                lines.append(diff)
                lines.append("```")
            else:
                lines.append("*No changes detected*")
        
        lines.append("")
        lines.append("</details>")
        lines.append("")
    
    # Approval instructions
    lines.append("---")
    lines.append("")
    lines.append("**To approve these changes**, react with 👍 to this comment or reply with `/approve`.")
    lines.append("")
    lines.append("This will create a branch `hal9000/issue-{issue_number}` with these changes.")
    
    return "\n".join(lines)


def post_comment(repo: str, issue_number: int, body: str) -> None:
    """Post a comment to a GitHub issue using gh CLI."""
    
    # GitHub has a comment size limit of 65536 characters
    if len(body) > 65000:
        body = body[:64000] + "\n\n*[Comment truncated due to size limits]*"
    
    result = subprocess.run(
        ["gh", "issue", "comment", str(issue_number), "--repo", repo, "--body", body],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error posting comment: {result.stderr}")
        raise RuntimeError(f"Failed to post comment: {result.stderr}")
    
    print(f"Successfully posted comment to issue #{issue_number}")


def main():
    parser = argparse.ArgumentParser(description="Post diff comment to GitHub issue")
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo", required=True)
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    
    # Load the response data
    response_path = output_dir / "response.json"
    if not response_path.exists():
        print(f"Error: {response_path} not found")
        return 1
    
    with open(response_path) as f:
        data = json.load(f)
    
    # Format the comment
    comment_body = format_diff_comment(
        changes=data.get("changes", []),
        explanation=data.get("explanation", "")
    )
    
    # Replace placeholder with actual issue number
    comment_body = comment_body.replace("{issue_number}", str(args.issue_number))
    
    # Post the comment
    post_comment(args.repo, args.issue_number, comment_body)
    
    # Save the comment for reference
    with open(output_dir / "comment.md", "w") as f:
        f.write(comment_body)
    
    return 0


if __name__ == "__main__":
    exit(main())
