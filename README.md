# Hal 9000 🤖

An AI-powered GitHub Actions workflow that automatically solves issues using LLMs.

Supports multiple providers via [LiteLLM](https://github.com/BerriAI/litellm):
- **Anthropic** (Claude Sonnet, Opus, Haiku)
- **Google** (Gemini 1.5 Pro, Flash)
- **OpenAI** (GPT-4o, GPT-4)
- **Stanford AI Gateway** (access to all above via Stanford's proxy)

## How It Works

1. Label an issue with `Hal 9000`
2. The workflow bundles your repo and sends it to the LLM with the issue description and comments
3. The model proposes code changes and runs your test suite
4. If tests fail, it retries up to 3 times with the error output
5. On success, it posts a collapsible diff comment on the issue
6. Choose how to proceed:
   - `/approve` or 👍 - Creates a branch only (you create the PR manually)
   - `/approve-pr` - Creates a branch AND a PR with an auto-generated description

### Re-running

If Hal 9000 fails or you add new context (comments, edited description), comment `/retry` on the issue to run it again. The new run will include all the latest comments and issue body.

## Planning Mode (Two-Phase)

For complex issues, you can use a two-phase approach:

1. **Planning Phase**: A smarter (potentially more expensive) model analyzes the issue and creates a detailed implementation plan
2. **Implementation Phase**: After you review and approve the plan, a (potentially cheaper) model executes it

This gives you more control and can be more cost-effective for complex tasks.

### Planning Mode Flow

1. Label an issue with `Hal 9000 Plan`
2. The planning model generates a detailed plan and posts it as a comment
3. Review the plan, then:
   - ✅ Comment `/approve-plan` to start implementation
   - 🔄 Comment `/retry-plan` to regenerate with updated context
   - ❌ Remove the label to cancel
4. Once implemented, react with 👍 or `/approve` to create the branch

### Planning Mode Setup

Copy [`examples/hal9000-with-planning.yml`](examples/hal9000-with-planning.yml) to your repo and configure:

```yaml
with:
  # Smart model for planning (does the thinking)
  planning_model: anthropic/claude-sonnet-4-20250514
  
  # Cost-effective model for implementation (does the coding)
  implementation_model: anthropic/claude-sonnet-4-20250514
```

**Model recommendations:**
- Planning: `anthropic/claude-sonnet-4-20250514` or `anthropic/claude-opus-4-20250514` for complex reasoning
- Implementation: `anthropic/claude-sonnet-4-20250514` or `anthropic/claude-haiku-3-5-20241022` for straightforward coding

### Re-running

If Hal 9000 fails or you add new context (comments, edited description), comment `/retry` on the issue to re-run with the updated information.

## Workflows

Hal 9000 offers two workflow options:

### Direct Execution (Simple)

Use `hal9000.yml` - labels trigger immediate implementation. Best for straightforward issues.

### Plan + Execute (Two-Phase)

Use `hal9000-with-planning.yml` - a more capable model creates a plan first, which you review before a faster model implements it. Best for complex issues.

**Flow:**
1. Label issue with `Hal 9000 Plan`
2. Planning model (e.g., Opus) generates detailed implementation plan
3. Review the plan posted as a comment
4. Execute the plan:
   - `/approve-plan` - Execute with up to 3 retry attempts
   - `/approve-plan-single` - Execute once only (cheaper/faster)
   - `/retry-plan` - Regenerate the plan
5. Execution model (e.g., Sonnet) implements the plan
6. Review the diff, then:
   - `/approve` to create just a branch
   - `/approve-pr` to create a branch AND PR with auto-generated description

This approach lets you use expensive models for thinking and cheaper models for coding.

## Quick Start

### 1. Set Up Secrets

Add these secrets to your organization (recommended) or repository:

| Secret | Required | Description |
|--------|----------|-------------|
| `LLM_API_KEY` | Yes | API key for your LLM provider (Stanford Gateway, Anthropic, OpenAI, etc.) |
| `PAT_TOKEN` | Yes | GitHub PAT with `repo` scope for creating branches |

**For Stanford users:** Use your AI API Gateway key as `LLM_API_KEY`.

### 2. Copy the Workflow

Copy one of the example workflows to `.github/workflows/` in your repository:

- [`examples/hal9000.yml`](examples/hal9000.yml) - Direct execution (simpler)
- [`examples/hal9000-with-planning.yml`](examples/hal9000-with-planning.yml) - Two-phase with planning

Update these values:

```yaml
# Change 'your-org' to your GitHub org/user
uses: your-org/hal9000-actions/.github/workflows/hal9000.yml@main

# Set your language
language: python  # or: react, java-spring

# Set your test command
test_command: pytest  # or: npm test, mvn test
```

### 3. Create an Issue and Label It

Create an issue describing what you want changed, then add the `Hal 9000` label.

## Configuration

### Workflow Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `language` | Yes | - | `python`, `react`, or `java-spring` |
| `test_command` | Yes | - | Command to run tests (e.g., `pytest`, `npm test`) |
| `model` | No | `anthropic/claude-sonnet-4-20250514` | LiteLLM model string (see below) |
| `api_base` | No | - | Custom API base URL (for Stanford Gateway or other proxies) |
| `max_retries` | No | `3` | Max attempts if tests fail |

**Model string examples:**
- `anthropic/claude-sonnet-4-20250514` - Claude Sonnet (default)
- `gemini/gemini-1.5-pro` - Google Gemini 1.5 Pro
- `openai/gpt-4o` - OpenAI GPT-4o

For Stanford AI Gateway, check the [AI API Gateway Rates page](https://uit.stanford.edu/service/ai-api-gateway/rates) for available models.

### Excluding Files

Create a `.hal9000ignore` file in your repo root to exclude files from the AI context:

```
# Exclude large generated files
generated/
*.min.js

# Exclude sensitive configs
.env.production
```

This works in addition to your `.gitignore`.

## Example Issue

**Title:** Add email validation to user registration

**Body:**
```
The user registration endpoint at `POST /api/users` should validate email addresses.

Requirements:
- Check that email has valid format (contains @ and domain)
- Return 400 with error message if invalid
- Add unit tests for the validation
```

## What Makes a Good Issue?

Hal 9000 works best with issues that are:

- **Specific** - Clear description of what needs to change
- **Scoped** - One focused task, not multiple unrelated changes
- **Testable** - Has clear success criteria that tests can verify

## Limitations

- Works best on smaller codebases (under ~50 files)
- Cannot access external services or APIs during execution
- May struggle with very complex refactoring tasks
- Test suite must be runnable in the GitHub Actions environment

## Costs

Each run uses approximately:
- Initial attempt: ~10-30K input tokens, ~2-4K output tokens
- Retries: Similar token counts per attempt

Costs vary by provider. For Stanford users, check the [AI API Gateway Rates](https://uit.stanford.edu/service/ai-api-gateway/rates).

## Contributing

Issues and PRs welcome! This is an experimental project.

## License

MIT
