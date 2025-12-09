#!/usr/bin/env python3
"""
Post the generated plan as a GitHub issue comment with approval instructions.
"""

import argparse
import json
import subprocess
from pathlib import Path


def format_plan_comment(plan_data: dict, implementation_model: str) -> str:
    """Format the plan as a GitHub markdown comment."""
    
    lines = []
    
    lines.append("## 🤖 Hal 9000 - Implementation Plan")
    lines.append("")
    
    # Summary
    if plan_data.get("summary"):
        lines.append("### Summary")
        lines.append("")
        lines.append(plan_data["summary"])
        lines.append("")
    
    # Steps
    if plan_data.get("steps"):
        lines.append("### Implementation Steps")
        lines.append("")
        for i, step in enumerate(plan_data["steps"], 1):
            lines.append(f"{i}. {step}")
        lines.append("")
    
    # Files to modify
    if plan_data.get("files_to_modify"):
        lines.append("### Files to Modify")
        lines.append("")
        for f in plan_data["files_to_modify"]:
            lines.append(f"- `{f}`")
        lines.append("")
    
    # Files to create
    if plan_data.get("files_to_create"):
        lines.append("### Files to Create")
        lines.append("")
        for f in plan_data["files_to_create"]:
            lines.append(f"- `{f}`")
        lines.append("")
    
    # Risks
    if plan_data.get("risks"):
        lines.append("### Risks & Considerations")
        lines.append("")
        for risk in plan_data["risks"]:
            lines.append(f"- {risk}")
        lines.append("")
    
    # Full plan in collapsible section
    lines.append("<details>")
    lines.append("<summary>📋 View Full Plan</summary>")
    lines.append("")
    lines.append(plan_data.get("raw_plan", "No detailed plan available."))
    lines.append("")
    lines.append("</details>")
    lines.append("")
    
    # Approval instructions
    lines.append("---")
    lines.append("")
    lines.append(f"**Implementation model:** `{implementation_model}`")
    lines.append("")
    lines.append("### Next Steps")
    lines.append("")
    lines.append("- ✅ **To approve this plan**, comment `/approve-plan`")
    lines.append("- 🔄 **To regenerate the plan**, comment `/retry-plan`")
    lines.append("- ❌ **To cancel**, remove the `Hal 9000 Plan` label")
    lines.append("")
    lines.append("Once approved, Hal 9000 will implement this plan and run tests.")
    
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
    
    print(f"Successfully posted plan comment to issue #{issue_number}")


def main():
    parser = argparse.ArgumentParser(description="Post plan comment to GitHub issue")
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--implementation-model", required=True)
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    
    # Load the plan data
    plan_path = output_dir / "plan.json"
    if not plan_path.exists():
        print(f"Error: {plan_path} not found")
        return 1
    
    with open(plan_path) as f:
        plan_data = json.load(f)
    
    # Format the comment
    comment_body = format_plan_comment(plan_data, args.implementation_model)
    
    # Post the comment
    post_comment(args.repo, args.issue_number, comment_body)
    
    # Save the comment for reference
    with open(output_dir / "plan_comment.md", "w") as f:
        f.write(comment_body)
    
    return 0


if __name__ == "__main__":
    exit(main())
