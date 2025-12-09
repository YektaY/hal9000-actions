#!/usr/bin/env python3
"""
Parse model response and apply file changes to the repository.
Expects model output in a structured format with file changes.
"""

import json
import re
from pathlib import Path


def parse_model_response(response_text: str) -> dict:
    """
    Parse the model's response to extract file changes and explanation.
    
    Expected format from model:
    
    ## Explanation
    <explanation text>
    
    ## Changes
    
    ### File: `path/to/file.py`
    ### Action: create|modify|delete
    ```python
    <file content>
    ```
    
    Or JSON format:
    ```json
    {
        "explanation": "...",
        "changes": [
            {"path": "...", "action": "create|modify|delete", "content": "..."}
        ]
    }
    ```
    """
    
    result = {
        "explanation": "",
        "changes": []
    }
    
    # Try to parse as JSON first (if model used JSON format)
    json_match = re.search(r"```json\s*\n(.*?)\n```", response_text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            if isinstance(parsed, dict) and "changes" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
    
    # Parse markdown format
    # Extract explanation
    explanation_match = re.search(
        r"##\s*Explanation\s*\n(.*?)(?=##\s*Changes|##\s*File:|$)",
        response_text,
        re.DOTALL | re.IGNORECASE
    )
    if explanation_match:
        result["explanation"] = explanation_match.group(1).strip()
    
    # Extract file changes
    # Pattern: ### File: `path` followed by ### Action: and code block
    file_pattern = re.compile(
        r"###?\s*File:\s*`([^`]+)`\s*\n"
        r"(?:###?\s*Action:\s*(\w+)\s*\n)?"
        r"```\w*\s*\n(.*?)```",
        re.DOTALL
    )
    
    for match in file_pattern.finditer(response_text):
        path = match.group(1)
        action = match.group(2) or "modify"  # Default to modify
        content = match.group(3)
        
        # Remove trailing newline from content if present
        if content.endswith("\n"):
            content = content[:-1]
        
        result["changes"].append({
            "path": path,
            "action": action.lower(),
            "content": content
        })
    
    # Alternative pattern: File: path (without backticks)
    if not result["changes"]:
        alt_pattern = re.compile(
            r"(?:###?\s*)?File:\s*([^\n`]+)\s*\n"
            r"(?:Action:\s*(\w+)\s*\n)?"
            r"```\w*\s*\n(.*?)```",
            re.DOTALL
        )
        
        for match in alt_pattern.finditer(response_text):
            path = match.group(1).strip()
            action = match.group(2) or "modify"
            content = match.group(3)
            
            if content.endswith("\n"):
                content = content[:-1]
            
            result["changes"].append({
                "path": path,
                "action": action.lower(),
                "content": content
            })
    
    # Pattern for delete actions (no code block needed)
    delete_pattern = re.compile(
        r"###?\s*File:\s*`?([^`\n]+)`?\s*\n"
        r"###?\s*Action:\s*delete",
        re.IGNORECASE
    )
    
    for match in delete_pattern.finditer(response_text):
        path = match.group(1).strip()
        # Check if we already have this file in changes
        existing_paths = [c["path"] for c in result["changes"]]
        if path not in existing_paths:
            result["changes"].append({
                "path": path,
                "action": "delete",
                "content": ""
            })
    
    return result


def apply_changes(changes: list[dict], repo_path: str) -> str:
    """
    Apply the parsed changes to the repository.
    Returns a summary of changes made.
    """
    
    repo_root = Path(repo_path)
    summary_lines = []
    
    for change in changes:
        path = change["path"]
        action = change.get("action", "modify")
        content = change.get("content", "")
        
        file_path = repo_root / path
        
        if action == "delete":
            if file_path.exists():
                file_path.unlink()
                summary_lines.append(f"🗑️  Deleted: {path}")
            else:
                summary_lines.append(f"⚠️  Skip delete (not found): {path}")
        
        elif action in ("create", "modify"):
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if file exists for summary
            existed = file_path.exists()
            
            # Write content
            file_path.write_text(content + "\n")  # Ensure trailing newline
            
            if existed:
                summary_lines.append(f"✏️  Modified: {path}")
            else:
                summary_lines.append(f"✨ Created: {path}")
        
        else:
            summary_lines.append(f"⚠️  Unknown action '{action}' for: {path}")
    
    return "\n".join(summary_lines)


def generate_diff(changes: list[dict], repo_path: str) -> dict[str, str]:
    """
    Generate diffs for each changed file.
    Returns a dict of {path: diff_content}.
    
    Note: This should be called BEFORE apply_changes to get proper diffs.
    """
    
    import subprocess
    
    repo_root = Path(repo_path)
    diffs = {}
    
    for change in changes:
        path = change["path"]
        action = change.get("action", "modify")
        content = change.get("content", "")
        
        file_path = repo_root / path
        
        if action == "delete":
            if file_path.exists():
                old_content = file_path.read_text()
                diffs[path] = {
                    "action": "delete",
                    "old": old_content,
                    "new": "",
                }
        
        elif action == "create":
            diffs[path] = {
                "action": "create",
                "old": "",
                "new": content,
            }
        
        elif action == "modify":
            old_content = ""
            if file_path.exists():
                old_content = file_path.read_text()
            
            diffs[path] = {
                "action": "modify",
                "old": old_content,
                "new": content,
            }
    
    return diffs


if __name__ == "__main__":
    # Test parsing
    test_response = '''
## Explanation

I've added a new utility function and fixed a bug in the main module.

## Changes

### File: `src/utils.py`
### Action: create
```python
def helper():
    return "hello"
```

### File: `src/main.py`
### Action: modify
```python
from utils import helper

def main():
    print(helper())
```
'''
    
    parsed = parse_model_response(test_response)
    print(json.dumps(parsed, indent=2))
