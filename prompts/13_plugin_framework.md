======================================================
ARCHITECTURE
======================================================

The agent MUST follow this lightweight structure.

ado2github-ai-migrator-agent

├── README.md
├── manifest.json
├── config.yaml
├── main.py
├── prompts.py
├── tools.py
├── tests/
│
├── schemas/
│   ├── discovery.py
│   ├── migration_plan.py
│   ├── github_actions.py
│   ├── validation.py
│   ├── report.py
│
├── templates/
│   ├── github_workflow.yml
│   ├── reusable_workflow.yml
│   ├── composite_action.yml
│
└── examples/

Do NOT introduce unnecessary frameworks.

Keep the code modular.

Use Python 3.12.

Follow SOLID principles.

Use Pydantic models.

Use type hints everywhere.

======================================================
IMPLEMENTATION REQUIREMENTS
======================================================

Generate production-ready code.

Generate complete source code.

Implement

main.py

prompts.py

tools.py

manifest.json

config.yaml

all schemas

README.md

unit tests

example inputs

example outputs

workflow templates

validation engine

migration planner

prompt library

The code must be clean, modular and documented.

======================================================
DEVELOPMENT APPROACH
======================================================

Build incrementally.

Step 1
Generate the complete repository structure.

Step 2
Generate configuration files.

Step 3
Generate schemas.

Step 4
Generate prompts.py.

Step 5
Generate tools.py.

Step 6
Generate main.py.

Step 7
Generate workflow templates.

Step 8
Generate validation engine.

Step 9
Generate migration planner.

Step 10
Generate README.

Do not skip steps.

Do not leave TODOs.

Do not generate placeholder implementations.

Every module must be fully functional.

Maintain compatibility with external orchestrators by keeping execution logic outside the SLM agent.

This project should be extensible so future connectors (GitLab, Bitbucket, Jenkins, Backstage, ServiceNow, ArgoCD, Terraform Cloud, Azure, AWS, GCP) can be added without modifying the core agent architecture.
