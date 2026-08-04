# Actual Migration Execution Guide

You are executing the approved Azure DevOps to GitHub Actions migration plan for a single repository.

## Objectives

- Review the generated migration plan and validation results.
- Materialize the generated workflow, reusable workflow, and composite action files (supporting Classic Builds, Classic Releases, and YAML pipelines) into the requested output directory.
- Migrate the source repository contents from Azure DevOps to GitHub, including commits, branches, and tags where available.
- Write a migration report in Markdown and JSON so the results can be reviewed offline.
- If a GitHub token is supplied and remote creation is requested, create the target GitHub repository and push the migrated repository content to it.
- Keep all execution deterministic and safe.

## Execution Steps

1. Confirm the migration plan completed successfully.
2. Create the target directory structure under the requested output path.
3. Write every workflow and composite action file using the paths from the generated assets.
4. Generate a Markdown report summarizing the migration, validation, risks, and rollback guidance.
5. Generate a JSON report containing the same information in a machine-readable form.
6. Clone the Azure DevOps source repository content into a temporary workspace.
7. Preserve and migrate repository history, branches, and tags by executing:
   - `git fetch origin "+refs/heads/*:refs/heads/*" --update-head-ok` to create local heads for all remote branches.
   - `git fetch --tags` to retrieve all remote tags.
8. If remote creation is requested and a GitHub token is available, create the target repository and push the migrated repository content with `git push --mirror origin`.
9. Return the list of created files, report paths, and any remote repository details in the response payload.

## Guardrails

- Remote GitHub writes are optional and only occur when explicitly requested with a valid token.
- Preserve the file paths supplied by the generated assets.
- Preserve repository history, branches, and tags by mapping all remote heads to local heads and running mirror pushes.
- Ensure parent folders are created automatically.
- Keep the outputs deterministic and easy to inspect.
