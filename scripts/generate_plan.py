#!/usr/bin/env python3
"""
Hal 9000 - Plan Generation Script
Uses a (potentially more expensive) model to create a detailed implementation plan
that can be reviewed and approved before implementation.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import litellm

from bundle_repo import bundle_repository


def load_planning_prompt() -> str:
    """Load the planning system prompt."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "planning_prompt.md"
    return prompt_path.read_text()


def build_planning_message(
    issue_title: str,
    issue_body: str,
    repo_contents: str,
    language: str,
    test_command: str,
    issue_comments: list[dict] | None = None,
) -> str:
    """Build the message for plan generation."""
    
    message = f"""## Issue to Plan

**Title:** {issue_title}

**Description:**
{issue_body}
"""
    
    if issue_comments:
        message += "\n**Discussion/Comments:**\n"
        for comment in issue_comments:
            author = comment.get("author", "unknown")
            body = comment.get("body", "")
            # Skip bot comments and approval commands
            if "Hal 9000" in body or body.strip() in ["/approve", "/retry", "👍"]:
                continue
            message += f"\n> **@{author}:** {body}\n"
    
    message += f"""
## Repository Context

**Language:** {language}
**Test Command:** `{test_command}`

## Codebase

{repo_contents}
"""
    
    return message


def call_llm(
    model: str,
    system_prompt: str,
    user_message: str,
    api_base: str | None = None,
) -> str:
    """Call the LLM API via LiteLLM and return the response."""
    
    kwargs = {}
    if api_base:
        kwargs["api_base"] = api_base
    
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        max_tokens=4096,
        **kwargs
    )
    
    usage = response.usage
    print(f"Token usage - Input: {usage.prompt_tokens}, Output: {usage.completion_tokens}")
    
    return response.choices[0].message.content


def parse_plan_response(response_text: str) -> dict:
    """Parse the planning response into structured data."""
    
    result = {
        "summary": "",
        "steps": [],
        "files_to_modify": [],
        "files_to_create": [],
        "tests_to_add": [],
        "risks": [],
        "raw_plan": response_text
    }
    
    # Try to extract structured sections
    import re
    
    # Extract summary
    summary_match = re.search(
        r"##\s*Summary\s*\n(.*?)(?=##|\Z)",
        response_text,
        re.DOTALL | re.IGNORECASE
    )
    if summary_match:
        result["summary"] = summary_match.group(1).strip()
    
    # Extract steps
    steps_match = re.search(
        r"##\s*(?:Implementation\s*)?Steps?\s*\n(.*?)(?=##|\Z)",
        response_text,
        re.DOTALL | re.IGNORECASE
    )
    if steps_match:
        steps_text = steps_match.group(1)
        # Parse numbered or bulleted list
        step_pattern = re.compile(r'(?:^|\n)\s*(?:\d+[\.\)]\s*|\*\s*|-\s*)(.*?)(?=\n\s*(?:\d+[\.\)]|\*|-)|$)', re.DOTALL)
        for match in step_pattern.finditer(steps_text):
            step = match.group(1).strip()
            if step:
                result["steps"].append(step)
    
    # Extract files to modify
    modify_match = re.search(
        r"##\s*Files?\s*to\s*Modify\s*\n(.*?)(?=##|\Z)",
        response_text,
        re.DOTALL | re.IGNORECASE
    )
    if modify_match:
        files_text = modify_match.group(1)
        file_pattern = re.compile(r'`([^`]+)`')
        result["files_to_modify"] = file_pattern.findall(files_text)
    
    # Extract files to create
    create_match = re.search(
        r"##\s*Files?\s*to\s*Create\s*\n(.*?)(?=##|\Z)",
        response_text,
        re.DOTALL | re.IGNORECASE
    )
    if create_match:
        files_text = create_match.group(1)
        file_pattern = re.compile(r'`([^`]+)`')
        result["files_to_create"] = file_pattern.findall(files_text)
    
    # Extract tests
    tests_match = re.search(
        r"##\s*Tests?\s*(?:to\s*Add)?\s*\n(.*?)(?=##|\Z)",
        response_text,
        re.DOTALL | re.IGNORECASE
    )
    if tests_match:
        result["tests_to_add"] = [tests_match.group(1).strip()]
    
    # Extract risks/considerations
    risks_match = re.search(
        r"##\s*(?:Risks?|Considerations?|Potential\s*Issues?)\s*\n(.*?)(?=##|\Z)",
        response_text,
        re.DOTALL | re.IGNORECASE
    )
    if risks_match:
        risks_text = risks_match.group(1)
        risk_pattern = re.compile(r'(?:^|\n)\s*(?:\d+[\.\)]\s*|\*\s*|-\s*)(.*?)(?=\n\s*(?:\d+[\.\)]|\*|-)|$)', re.DOTALL)
        for match in risk_pattern.finditer(risks_text):
            risk = match.group(1).strip()
            if risk:
                result["risks"].append(risk)
    
    return result


def save_plan(output_dir: Path, plan_data: dict, implementation_model: str) -> None:
    """Save the plan for later use."""
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Add implementation model to plan data
    plan_data["implementation_model"] = implementation_model
    
    with open(output_dir / "plan.json", "w") as f:
        json.dump(plan_data, f, indent=2)
    
    with open(output_dir / "plan_raw.md", "w") as f:
        f.write(plan_data["raw_plan"])


def main():
    parser = argparse.ArgumentParser(description="Hal 9000 Plan Generator")
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--issue-title", required=True)
    parser.add_argument("--issue-body", required=True)
    parser.add_argument("--issue-comments-file", required=False, default=None)
    parser.add_argument("--language", required=True)
    parser.add_argument("--test-command", required=True)
    parser.add_argument("--model", default="anthropic/claude-sonnet-4-20250514")
    parser.add_argument("--implementation-model", default="anthropic/claude-sonnet-4-20250514")
    parser.add_argument("--api-base", default=None)
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--output-dir", required=True)
    
    args = parser.parse_args()
    
    print(f"Generating plan using: {args.model}")
    print(f"Implementation will use: {args.implementation_model}")
    
    # Load system prompt
    system_prompt = load_planning_prompt()
    
    # Bundle the repository
    print("Bundling repository contents...")
    repo_contents = bundle_repository(args.repo_path)
    
    # Load issue comments if provided
    issue_comments = None
    if args.issue_comments_file:
        comments_path = Path(args.issue_comments_file)
        if comments_path.exists():
            with open(comments_path) as f:
                issue_comments = json.load(f)
            print(f"Loaded {len(issue_comments)} issue comments")
    
    # Build the message
    user_message = build_planning_message(
        issue_title=args.issue_title,
        issue_body=args.issue_body,
        repo_contents=repo_contents,
        language=args.language,
        test_command=args.test_command,
        issue_comments=issue_comments,
    )
    
    try:
        # Call the planning model
        print("Calling planning model...")
        response_text = call_llm(
            model=args.model,
            system_prompt=system_prompt,
            user_message=user_message,
            api_base=args.api_base,
        )
        
        # Parse the plan
        print("Parsing plan...")
        plan_data = parse_plan_response(response_text)
        
        # Save the plan
        output_dir = Path(args.output_dir)
        save_plan(output_dir, plan_data, args.implementation_model)
        
        print("✅ Plan generated successfully")
        
        # Set output for GitHub Actions
        with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
            f.write("success=true\n")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error generating plan: {e}")
        
        with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
            f.write("success=false\n")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
