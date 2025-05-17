# Junk Data Generator

This project automates the creation of junk repositories and files for a GitHub organization or a single repository.

## Prerequisites

Before running this script, ensure you have:

- Python **3.x** installed
- `pip` installed
- A **GitHub Personal Access Token** with appropriate permissions
- The following Python dependencies:

  ```sh
  pip install PyGithub
  ```

- A valid **`config.txt`** file in the same directory as the script, containing:

  ```
  GITHUB_TOKEN=your_personal_access_token_here
  ORG_NAME=your_organization_name_here  # For org-based script
  REPO_NAME=your-repo-name  # For repo-based script
  REPO_DESCRIPTION=Repository filled with junk content
  PRIVATE_REPO=False
  FILE_NAME_PREFIX=junk-
  FILE_EXTENSION=txt
  ```

## Running the Scripts

### Organization Junk Data Generator

This script generates multiple repositories within a GitHub organization, each populated with junk files.

Run the command:

```sh
./run
```

### Repository Junk Data Generator

This script populates a single repository with junk files.

Run the command:

```sh
./run2
```

## Execution Modes

When running either script, you will be prompted to choose execution speed:

- **SUPER FAST**: Uses maximum concurrency (fast execution but may hit rate limits).
- **SLOW**: Reduces concurrency and adds slight delays to avoid rate-limiting issues.

## Troubleshooting

- Ensure your **GitHub token** has the necessary scopes (`repo` for personal repositories, `admin:org` for organization repositories).
- If you receive **403 Forbidden errors**, check if your token permissions need adjustment.
- If you hit **GitHub rate limits**, try running in **SLOW** mode.

---

This should give a clear overview of how everything works! Let me know if you need further tweaks.