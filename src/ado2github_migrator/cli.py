import argparse

from .application.service import MigrationService
from .domain.models import RepositoryRef
from .infrastructure.memory_store import InMemoryMigrationRunStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Repository-scoped Azure DevOps to GitHub migration platform")
    parser.add_argument(
        "command",
        choices=("discover", "analyze", "plan", "migrate", "validate", "rollback", "report", "sync", "resume", "export", "import"),
    )
    parser.add_argument("--ado-organization", required=True)
    parser.add_argument("--ado-project", required=True)
    parser.add_argument("--ado-repository", required=True)
    parser.add_argument("--github-organization", required=True)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--execute", action="store_true", help="Create a non-dry-run record; it does not perform remote writes.")
    args = parser.parse_args()

    service = MigrationService(InMemoryMigrationRunStore())
    run = service.create_run(
        RepositoryRef(args.ado_organization, args.ado_repository, args.ado_project),
        RepositoryRef(args.github_organization, args.github_repository),
        dry_run=not args.execute,
    )
    print(f"Created repository-scoped {args.command} run {run.id} (dry_run={run.dry_run}).")
    print("No remote operation is implemented or performed by this scaffold command.")


if __name__ == "__main__":
    main()
