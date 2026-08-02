# Generate Complete Project Code

You are the implementation agent for the project **ado2github-ai-migrator-agent**.

Your task is to generate the complete production-ready source code for this repository.

## Rules

- Read and follow `prompts/system_prompt.md` before generating any code.
- All generated code must comply with the architecture, conventions, and responsibilities defined in the system prompt.
- Do not change the repository structure unless explicitly required.
- Never use placeholder implementations or TODO comments.
- Generate fully working code with documentation and unit tests.
- Use Python 3.12.
- Use Pydantic for schemas.
- Use type hints throughout.
- Follow SOLID principles.
- Keep the SLM focused on reasoning only; all execution must remain external to the agent.

## Repository Layout

Generate code for the following folders and files.

```
README.md
manifest.json
config.yaml
main.py
prompts.py
tools.py

schemas/
templates/
tests/
examples/
```

If a directory does not exist, create it.

## Implementation Order

Generate the project incrementally.

### Phase 1

Generate

- README.md
- manifest.json
- config.yaml

### Phase 2

Generate

- prompts.py
- Prompt loader
- Prompt manager
- Prompt cache

### Phase 3

Generate schemas

- discovery.py
- migration_plan.py
- github_actions.py
- validation.py
- report.py

### Phase 4

Generate tools.py

Include tool definitions only.

No execution logic.

Return structured tool metadata compatible with an external orchestrator.

### Phase 5

Generate main.py

Implement

- Agent entry point
- Prompt loading
- Request validation
- JSON output generation
- Error handling
- Logging
- Tool registration
- Configuration loading

### Phase 6

Generate workflow templates

- github_workflow.yml
- reusable_workflow.yml
- composite_action.yml

### Phase 7

Generate migration planner

Implement planners for

- Git repositories
- Build pipelines
- Release pipelines
- Variables
- Secrets
- Environments
- Runner mapping
- Service connections
- Validation

### Phase 8

Generate validation engine

Validate

- Git repositories
- Branches
- Tags
- Commit history
- Pipelines
- Variables
- Secrets
- Runner mapping
- GitHub workflow syntax

### Phase 9

Generate reporting engine

Reports

- Migration
- Validation
- Risks
- Unsupported features
- Rollback
- Executive summary

### Phase 10

Generate unit tests

Cover every public class and function.

### Phase 11

Generate example input and output JSON.

### Phase 12

Review the entire project.

Ensure

- Imports are correct
- No dead code
- No duplicate logic
- No placeholders
- No missing files
- All modules integrate correctly

## Coding Standards

Generate enterprise-quality code.

Use

- dataclasses only where appropriate
- Pydantic models
- Enums
- TypedDict when beneficial
- Logging
- Exception handling
- Configuration abstraction

Avoid

- Global mutable state
- Circular imports
- Hard-coded values
- Business logic in main.py

## Expected Output

Generate one complete file at a time.

For every file include:

1. File path
2. Purpose
3. Complete source code

After each file, wait for the next generation request unless explicitly instructed to continue automatically.

Never skip files.

Never summarize code.

Always generate production-ready implementations.