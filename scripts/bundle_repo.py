#!/usr/bin/env python3
"""
Bundle repository contents into a single string for LLM context.
Respects .gitignore and .hal9000ignore, skips binary files.
"""

import os
from pathlib import Path
from fnmatch import fnmatch

# Default patterns to always ignore
DEFAULT_IGNORE = [
    ".git",
    ".git/**",
    ".hal9000",
    ".hal9000/**",
    ".hal9000-output",
    ".hal9000-output/**",
    "__pycache__",
    "__pycache__/**",
    "*.pyc",
    ".pytest_cache",
    ".pytest_cache/**",
    "node_modules",
    "node_modules/**",
    ".next",
    ".next/**",
    "target",
    "target/**",
    ".idea",
    ".idea/**",
    ".vscode",
    ".vscode/**",
    "*.lock",
    "package-lock.json",
    "*.min.js",
    "*.min.css",
    "dist/**",
    "build/**",
    ".env",
    ".env.*",
    "*.log",
    "*.sqlite",
    "*.db",
]

# Binary file extensions to skip
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".jar", ".class", ".war",
    ".pyc", ".pyo", ".pyd",
}

# Max file size to include (100KB)
MAX_FILE_SIZE = 100 * 1024


def load_ignore_patterns(repo_path: str) -> list[str]:
    """Load ignore patterns from .gitignore and .hal9000ignore."""
    
    patterns = DEFAULT_IGNORE.copy()
    
    # Load .gitignore
    gitignore_path = Path(repo_path) / ".gitignore"
    if gitignore_path.exists():
        for line in gitignore_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    
    # Load .hal9000ignore (additional exclusions specific to Hal 9000)
    hal_ignore_path = Path(repo_path) / ".hal9000ignore"
    if hal_ignore_path.exists():
        for line in hal_ignore_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    
    return patterns


def should_ignore(path: Path, patterns: list[str], repo_root: Path) -> bool:
    """Check if a path should be ignored based on patterns."""
    
    rel_path = str(path.relative_to(repo_root))
    
    for pattern in patterns:
        # Check exact match
        if fnmatch(rel_path, pattern):
            return True
        # Check basename match
        if fnmatch(path.name, pattern):
            return True
        # Check if any parent directory matches
        for parent in path.relative_to(repo_root).parents:
            if fnmatch(str(parent), pattern):
                return True
    
    return False


def is_binary_file(path: Path) -> bool:
    """Check if a file is binary based on extension or content."""
    
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    
    # Try to detect binary content
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
            # Check for null bytes (common in binary files)
            if b"\x00" in chunk:
                return True
    except Exception:
        return True
    
    return False


def get_file_content(path: Path) -> str | None:
    """Read file content, return None if unable to read."""
    
    if path.stat().st_size > MAX_FILE_SIZE:
        return f"[File too large: {path.stat().st_size} bytes]"
    
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except Exception:
            return None
    except Exception:
        return None


def bundle_repository(repo_path: str) -> str:
    """Bundle all repository files into a formatted string."""
    
    repo_root = Path(repo_path).resolve()
    patterns = load_ignore_patterns(repo_path)
    
    files_content = []
    file_count = 0
    total_size = 0
    
    # Walk the repository
    for root, dirs, files in os.walk(repo_root):
        root_path = Path(root)
        
        # Filter out ignored directories (modifies dirs in-place)
        dirs[:] = [
            d for d in dirs
            if not should_ignore(root_path / d, patterns, repo_root)
        ]
        
        for filename in sorted(files):
            file_path = root_path / filename
            
            # Skip ignored files
            if should_ignore(file_path, patterns, repo_root):
                continue
            
            # Skip binary files
            if is_binary_file(file_path):
                continue
            
            # Get relative path
            rel_path = file_path.relative_to(repo_root)
            
            # Read content
            content = get_file_content(file_path)
            if content is None:
                continue
            
            # Format the file entry
            files_content.append(f"### File: `{rel_path}`\n\n```\n{content}\n```")
            
            file_count += 1
            total_size += len(content)
    
    # Build the final bundle
    header = f"Repository contains {file_count} files ({total_size:,} characters)\n\n"
    
    return header + "\n\n---\n\n".join(files_content)


def get_file_tree(repo_path: str) -> str:
    """Generate a simple file tree representation."""
    
    repo_root = Path(repo_path).resolve()
    patterns = load_ignore_patterns(repo_path)
    
    lines = []
    
    def walk_dir(path: Path, prefix: str = ""):
        entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
        
        for i, entry in enumerate(entries):
            if should_ignore(entry, patterns, repo_root):
                continue
            
            is_last = i == len(entries) - 1
            current_prefix = "└── " if is_last else "├── "
            lines.append(f"{prefix}{current_prefix}{entry.name}")
            
            if entry.is_dir():
                next_prefix = prefix + ("    " if is_last else "│   ")
                walk_dir(entry, next_prefix)
    
    walk_dir(repo_root)
    
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: bundle_repo.py <repo_path>")
        sys.exit(1)
    
    repo_path = sys.argv[1]
    
    print("File tree:")
    print(get_file_tree(repo_path))
    print("\n" + "="*50 + "\n")
    
    bundle = bundle_repository(repo_path)
    print(f"Bundle size: {len(bundle):,} characters")
