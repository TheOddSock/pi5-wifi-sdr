# Preparing a release for publication

The package separates reader-facing version labels from publication approval. A prepared version can be reviewed locally without asserting public availability. Author identities, contributions and the canonical repository URL must be supplied before publication.

Use `tools/finalise_release.py template --source SOURCE --output CONFIG.json` to produce a configuration for the exact source manifest. Fill the creator names, contributions, version, title, source URL and preparation date. Carry forward the selected licence scopes and assign every final file explicitly; do not relicense upstream material. The template contains unset metadata so it cannot accidentally authorise publication.

Run `tools/finalise_release.py prepare --source SOURCE --config CONFIG.json --output FRESH_OUTPUT`. The output must be isolated and new. Preparation copies only manifested files, renders the report, rebuilds the static site and binds the exact output files. Review the PDF, site, component map, tests and content digest.

The separate `approve` command requires both the exact reviewed content digest and `--owner-approved`. Use it only after the owner approves that exact output. It changes local approval records, never uploads files. `tools/verify_release.py --publish` checks the local publication gate. Actual repository, hosting and archival publication are separate actions.

After publication, record actual availability and any assigned identifiers in a new tracked metadata revision. Preserve the approved report and released asset bytes. Do not infer a public date from a preparation date.
