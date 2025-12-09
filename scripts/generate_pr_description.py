#!/usr/bin/env python3
"""
Generate a PR description using a cheap/fast LLM model.
"""

import argparse
import json
from pathlib import Path

import litellm


PR_SYSTEM_PROMPT = """You are a helpful assistant that writes clear, concise pull request descriptions.

Given information about a GitHub issue and the code changes made to solve it, write a professional PR description.

## Output Format

Write the PR description in markdown with these sections:

## Summary
A 1-2 sentence overview of what this PR does.

## Changes
A bullet list of the key changes made:
- Change 1
- Change 2
- ...

## Testing
Brief note on how this was tested (mention if unit tests were added).

## Related Issue
Closes #<issue_number>

## Guidelines

- Be concise - developers are busy
- Focus on WHAT changed and WHY, not HOW (the code shows how)
- Don't repeat the full issue description
- Don't include implementation details that are obvious from the diff
- Use present tense ("Add feature" not "Added feature")
- Keep the total length under 300 words
"""


def generate_pr_description(
    issue_data: dict,
    changes_data: dict,
    model: str,
    api_base: str | None = None,
) -> str:
    """Generate a PR description using the LLM."""
    
    issue_number = issue_data.get("number", "?")
    issue_title = issue_data.get("title", "Unknown")
    issue_body = issue_data.get("body", "No description provided.")
    
    # Build a summary of changes
    changes = changes_data.get("changes", [])
    explanation = changes_data.get("explanation", "")
    
    files_changed = []
    for change in changes:
        path = change.get("path", "unknown")
        action = change.get("action", "modify")
        files_changed.append(f"- `{path}` ({action})")
    
    files_summary = "\n".join(files_changed) if files_changed else "No files listed"
    
    user_message = f"""## Issue Information

**Issue #{issue_number}:** {issue_title}

**Description:**
{issue_body}

## Changes Made

**Files:**
{files_summary}

**Explanation from implementation:**
{explanation}

---

Write a PR description for these changes.
"""
    
    kwargs = {}
    if api_base:
        kwargs["api_base"] = api_base
    
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": PR_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        max_tokens=1024,
        **kwargs
    )
    
    usage = response.usage
    print(f"Token usage - Input: {usage.prompt_tokens}, Output: {usage.completion_tokens}")
    
    pr_description = response.choices[0].message.content
    
    # Ensure the "Closes #X" is correct
    if f"#{issue_number}" not in pr_description:
        pr_description += f"\n\n---\nCloses #{issue_number}"
    
    return pr_description


def main():
    parser = argparse.ArgumentParser(description="Generate PR description")
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--issue-file", required=True, help="Path to issue JSON file")
    parser.add_argument("--output-dir", required=True, help="Path to hal9000 output dir")
    parser.add_argument("--model", default="anthropic/claude-haiku-3-5-20241022")
    parser.add_argument("--api-base", default=None)
    parser.add_argument("--output-file", required=True, help="Where to write the PR description")
    
    args = parser.parse_args()
    
    # Load issue data
    issue_path = Path(args.issue_file)
    if not issue_path.exists():
        print(f"Error: Issue file not found at {issue_path}")
        return 1
    
    with open(issue_path) as f:
        issue_data = json.load(f)
    
    # Load changes data
    output_dir = Path(args.output_dir)
    response_path = output_dir / "response.json"
    
    changes_data = {}
    if response_path.exists():
        with open(response_path) as f:
            changes_data = json.load(f)
    
    print(f"Generating PR description with model: {args.model}")
    
    try:
        pr_description = generate_pr_description(
            issue_data=issue_data,
            changes_data=changes_data,
            model=args.model,
            api_base=args.api_base,
        )
        
        # Write to output file
        output_path = Path(args.output_file)
        output_path.write_text(pr_description)
        
        print(f"✅ PR description written to {output_path}")
        return 0
        
    except Exception as e:
        print(f"❌ Error generating PR description: {e}")
        
        # Write a fallback description
        fallback = f"""## Summary

Automated changes for issue #{args.issue_number}.

## Changes

See the diff for details.

## Related Issue

Closes #{args.issue_number}
"""
        Path(args.output_file).write_text(fallback)
        print("Wrote fallback PR description")
        return 0  # Don't fail the workflow


if __name__ == "__main__":
    exit(main())
