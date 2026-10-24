# Implementation notes

- Target repository: `jorgeezequiel/jorgeezequiel` (must be created first if absent).
- The GitHub connector available in this session does not expose a create-repository action.
- No GitHub repository, workflow, secret, token, or commit was created by this kit.
- The workflow uses the built-in `GITHUB_TOKEN` and requests only `contents: write`.
- The script collects public repository language metadata only; it does not fetch code or private repository information.
- Explicit privacy/site repositories are excluded, as are archived repos, forks, and repository names/topics matching privacy-policy indicators.
- The script exits before writing tracked outputs if collection fails or produces no eligible language data.
- Review the exclusion rules and workflow actions before first run. The first successful run creates `assets/language-stats.gif` and replaces the README stats placeholder.
