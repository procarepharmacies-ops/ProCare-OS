# Changelog

Repository: procarepharmacies-ops/ProCare-OS

Description: ProCare OS — independent pharmacy operating system (own SQL Server DB) mirroring eStock + Titan/Drug-Eye, with AI & automation. Arabic-first, multi-branch (Main + Elsanta).

Language composition:
- Python: 64%
- JavaScript: 29.2%
- TSQL: 3%
- Batchfile: 1.7%
- Shell: 1.2%
- CSS: 0.9%

---

## v0.1.0 — Initial release (2026-08-17)

Initial private release of ProCare OS.

Highlights
- Initial backend in Python and frontend scaffolding in JavaScript.
- T-SQL scripts and integration points for SQL Server.
- Arabic-first UI/UX and multi-branch support (Main + Elsanta).
- CI configs and initial automation & AI scaffolding included.

Notes
- This is the repository's first release tag (v0.1.0). Tag and GitHub Release are not created by this commit — use the commands below to create the Git tag and Release on GitHub.

Commands to create the GitHub Release (run locally or in CI)

Using GitHub CLI (recommended):

gh release create v0.1.0 \
  --title "v0.1.0 — Initial release" \
  --notes "Initial private release of ProCare OS. Includes Python backend, JavaScript frontend scaffolding, and T-SQL scripts for SQL Server integration." \
  --target main

Using curl (GitHub API) — set GITHUB_TOKEN with repo scope first:

curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tag_name": "v0.1.0",
    "target_commitish": "main",
    "name": "v0.1.0 — Initial release",
    "body": "Initial private release of ProCare OS. Includes Python backend, JavaScript frontend scaffolding, and T-SQL scripts for SQL Server integration.",
    "draft": false,
    "prerelease": false
  }' \
  https://api.github.com/repos/procarepharmacies-ops/ProCare-OS/releases

If you want me to also create the Git tag and GitHub Release directly, I can attempt to create the tag and release, but I will need your confirmation and an indication that I have the necessary permissions (or you can run the gh/curl commands yourself).