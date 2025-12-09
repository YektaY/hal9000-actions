#!/usr/bin/env python3
"""
Hal 9000 - Main orchestration script
Sends issue + codebase to LLM API, applies changes, runs tests with retry loop.
Supports multiple providers via LiteLLM (Anthropic, OpenAI, Gemini, etc.)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import litellm

from bundle_repo import bundle_repository
from apply_changes import apply_changes, parse_model_response


def load_system_prompt() -> str:
    """Load the system prompt from the prompts directory."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "system_prompt.md"
    return prompt_path.read_text()


def build_user_message(
    issue_title: str,
    issue_body: str,
    repo_contents: str,
    language: str,
    test_command: str,
    issue_comments: list[dict] | None = None,
    previous_attempt: dict | None = None,
) -> str:
    """Build the user message with issue and repo context."""
    
    message = f"""## Issue to Solve

**Title:** {issue_title}

**Description:**
{issue_body}
"""
    
    # Add comments if present
    if issue_comments:
        message += "\n**Discussion/Comments:**\n"
        for comment in issue_comments:
            author = comment.get("author", "unknown")
            body = comment.get("body", "")
            message += f"\n> **@{author}:** {body}\n"
    
    message += f"""
## Repository Context

**Language:** {language}
**Test Command:** `{test_command}`

## Codebase

{repo_contents}
"""
    
    if previous_attempt:
        message += f"""
## Previous Attempt Failed

Your previous changes caused test failures. Here's what happened:

**Test Output:**
```
{previous_attempt['test_output']}
```

**Your Previous Changes:**
{previous_attempt['changes_summary']}

Please analyze the failures and provide corrected changes.
"""
    
    return message


def call_llm(
    model: str,
    system_prompt: str,
    user_message: str,
    api_base: str | None = None,
    max_rate_limit_retries: int = 5,
) -> str:
    """Call the LLM API via LiteLLM with rate limit retry."""
    
    # Set API base if provided (for Stanford AI Gateway or other proxies)
    kwargs = {}
    if api_base:
        kwargs["api_base"] = api_base
    
    for attempt in range(max_rate_limit_retries):
        try:
            response = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=8192,
                **kwargs
            )
            
            # Log token usage
            usage = response.usage
            print(f"Token usage - Input: {usage.prompt_tokens}, Output: {usage.completion_tokens}")
            
            return response.choices[0].message.content
            
        except Exception as e:
            error_str = str(e).lower()
            if "rate_limit" in error_str or "429" in error_str or "too many requests" in error_str:
                wait_time = (2 ** attempt) * 30  # 30s, 60s, 120s, 240s, 480s
                print(f"⏳ Rate limit hit. Waiting {wait_time} seconds before retry ({attempt + 1}/{max_rate_limit_retries})...")
                time.sleep(wait_time)
            else:
                raise
    
    raise Exception(f"Rate limit exceeded after {max_rate_limit_retries} retries")


def run_tests(test_command: str, repo_path: str) -> tuple[bool, str]:
    """Run the test command and return (success, output)."""
    
    try:
        result = subprocess.run(
            test_command,
            shell=True,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        
        output = result.stdout + "\n" + result.stderr
        success = result.returncode == 0
        
        return success, output.strip()
    
    except subprocess.TimeoutExpired:
        return False, "Test command timed out after 5 minutes"
    except Exception as e:
        return False, f"Error running tests: {str(e)}"


def save_output(output_dir: Path, data: dict) -> None:
    """Save the output data for downstream steps."""
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the full response data
    with open(output_dir / "response.json", "w") as f:
        json.dump(data, f, indent=2)
    
    # Save individual files for easy access
    if "changes" in data:
        with open(output_dir / "changes.json", "w") as f:
            json.dump(data["changes"], f, indent=2)
    
    if "explanation" in data:
        with open(output_dir / "explanation.md", "w") as f:
            f.write(data["explanation"])


def main():
    parser = argparse.ArgumentParser(description="Hal 9000 AI Coding Agent")
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--issue-title", required=True)
    parser.add_argument("--issue-body", required=True)
    parser.add_argument("--issue-comments-file", required=False, default=None)
    parser.add_argument("--language", required=True)
    parser.add_argument("--test-command", required=True)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--model", default="anthropic/claude-sonnet-4-20250514",
                        help="LiteLLM model string (e.g., anthropic/claude-sonnet-4-20250514, gemini/gemini-1.5-pro, openai/gpt-4o)")
    parser.add_argument("--api-base", default=None,
                        help="Custom API base URL (e.g., Stanford AI Gateway URL)")
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--output-dir", required=True)
    
    args = parser.parse_args()
    
    # Load system prompt
    system_prompt = load_system_prompt()
    
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
    
    # Main retry loop
    previous_attempt = None
    success = False
    
    for attempt in range(1, args.max_retries + 1):
        print(f"\n{'='*50}")
        print(f"Attempt {attempt}/{args.max_retries}")
        print(f"Model: {args.model}")
        print('='*50)
        
        # Build the user message
        user_message = build_user_message(
            issue_title=args.issue_title,
            issue_body=args.issue_body,
            repo_contents=repo_contents,
            language=args.language,
            test_command=args.test_command,
            issue_comments=issue_comments,
            previous_attempt=previous_attempt,
        )
        
        # Call the API
        print("Calling LLM API...")
        response_text = call_llm(
            model=args.model,
            system_prompt=system_prompt,
            user_message=user_message,
            api_base=args.api_base,
        )
        
        # Parse the response
        print("Parsing model response...")
        parsed = parse_model_response(response_text)
        
        if not parsed["changes"]:
            print("Error: Model did not provide any changes")
            previous_attempt = {
                "test_output": "Model did not provide any file changes",
                "changes_summary": response_text[:1000],
            }
            continue
        
        # Apply changes to the repository
        print("Applying changes to repository...")
        changes_summary = apply_changes(parsed["changes"], args.repo_path)
        print(changes_summary)
        
        # Run tests
        print(f"Running tests: {args.test_command}")
        test_success, test_output = run_tests(args.test_command, args.repo_path)
        
        if test_success:
            print("✅ Tests passed!")
            success = True
            
            # Save successful output
            output_dir = Path(args.output_dir)
            save_output(output_dir, {
                "success": True,
                "attempt": attempt,
                "changes": parsed["changes"],
                "explanation": parsed.get("explanation", ""),
                "test_output": test_output,
            })
            
            break
        else:
            print(f"❌ Tests failed on attempt {attempt}")
            print(f"Test output:\n{test_output[:2000]}")
            
            # Prepare for retry
            previous_attempt = {
                "test_output": test_output,
                "changes_summary": changes_summary,
            }
            
            # Revert changes for next attempt (re-checkout)
            if attempt < args.max_retries:
                print("Reverting changes for next attempt...")
                subprocess.run(
                    ["git", "checkout", "."],
                    cwd=args.repo_path,
                    capture_output=True,
                )
    
    if not success:
        print(f"\n❌ Failed after {args.max_retries} attempts")
        
        # Save failure output
        output_dir = Path(args.output_dir)
        save_output(output_dir, {
            "success": False,
            "attempts": args.max_retries,
            "last_test_output": previous_attempt["test_output"] if previous_attempt else "Unknown error",
        })
    
    # Set output for GitHub Actions
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
        f.write(f"success={'true' if success else 'false'}\n")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
