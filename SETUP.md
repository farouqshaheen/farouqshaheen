# Install — Clean ONI Profile V2

This version uses **two animated sections only**: the existing ONI field scene and a contribution calendar that ONI traverses. Other project graphics are static. The header stays unchanged.

## Upload files

Repository: **https://github.com/farouqshaheen/farouqshaheen** on branch **main**.

Preserve the following paths exactly:

```text
farouqshaheen/
├── README.md
├── farouq-header-onyx.png
├── assets/
│   ├── oni-field-operations.svg
│   ├── oni-contributions.svg       <- starts with an honest "awaiting sync" placeholder
│   ├── oni-avatar.png              <- source image of the ONI mascot
│   ├── case-invisible-leak.svg     <- static
│   ├── case-phantom-protocol.svg   <- static
│   └── focus-map.svg              <- static
├── scripts/
│   └── generate_oni_contributions.py
└── .github/workflows/
    └── oni-contributions.yml
```

The workflow writes `assets/oni-contributions.svg` daily (02:37 UTC) from your **actual** GitHub contribution calendar. Initially, the SVG says **AWAITING FIRST GITHUB ACTION SYNC**, because no live data has been fetched yet. Do not substitute the bundled design-sample fixture for the real output.

## First-time sync

1. Commit all files to the repository's default branch (`main`).
2. Open the repository's **Actions** tab. If Actions are disabled, enable them for this repository.
3. Select **ONI Contribution Trail** in the left sidebar and choose **Run workflow**, on branch `main`.
4. Confirm the workflow succeeds. It should produce a commit named `chore(profile): refresh ONI contribution trail` and replace the placeholder.
5. Refresh your [GitHub profile](https://github.com/farouqshaheen) to view the updated animation. GitHub's image cache may take a little while to refresh.

No personal access token or repository secret is normally needed; GitHub supplies `GITHUB_TOKEN` to the Action. If it fails to push, check **Settings → Actions → General → Workflow permissions** and any branch protections; the workflow itself requests `contents: write`. If querying GitHub's contribution GraphQL API fails, read the Action logs rather than inventing activity values.

## GitHub via terminal (recommended for nested folders)

Copy the files/folders into a local clone, then run:

```bash
git add README.md farouq-header-onyx.png assets scripts .github/workflows/oni-contributions.yml
git commit -m "feat(profile): add clean ONI contribution trail"
git push origin main
```

## Design / privacy notes

- The calendar includes one year of contribution **counts only**. It doesn't reveal private repository code or secrets. Exact public/private totals may differ depending on GitHub visibility and what `GITHUB_TOKEN` can access.
- The ONI avatar is embedded in the output SVG so GitHub can display it without external file references. The original layered character assets are not required in the profile repository.
- The animation uses built-in SVG motion (`animateTransform`), not JavaScript. Support varies by viewer/browser and GitHub image proxy handling; verify it in your actual profile. A stable ONI image remains visible if animation doesn't run.
- README's optional stats cards and the profile-view badge are third-party services; they can fail independently of the contribution calendar.
- The separate `design-preview.png` / `design-preview.gif` show **example data**, not actual account activity. Do not put these demo files in the README as the live graph.
