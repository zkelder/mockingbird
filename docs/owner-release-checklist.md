# Owner Pre-Publication Checklist (1.0)

Items only the repository owner can do or decide. Nothing here has been done
by engineering work: no tag, push, GitHub release, signing certificate, domain
or trademark exists as of this document. See also
[release-execution-state.md](release-execution-state.md) §3 (authorization) and
[support-matrix.md](support-matrix.md).

## Required before publishing

1. **Decide the release version.** Final Release Hardening & Launch Candidate
   v1 was authorized and validated at `0.1.0` without a bump; whether to bump
   from `0.1.0` to `1.0.0` is still an owner decision. A bump touches
   `pyproject.toml`, `mockingbird.__init__._DEV_CHECKOUT_FALLBACK_VERSION`,
   `mockingbird_node.__version__` and `web/package.json`
   (`tests/test_version_provenance.py` keeps them in sync) and requires
   rebuilding and re-accepting the ZIP; the candidate report lists the
   validation to repeat.
2. **Authorize the push** of `main` to GitHub. Local `main` is ahead of
   `origin/main` by dozens of commits (41 when Final Release Hardening & Launch
   Candidate v1 began; run `git rev-list --count origin/main..main` for the
   current number); nothing has been pushed.
3. **Build and accept the final artifacts** at the final commit:
   `MockingBird-windows-x64.zip`, `SHA256SUMS`, and the Camera Node artifact,
   with native-Windows acceptance of that exact build.
4. **Publish a GitHub Release** with those artifacts and `SHA256SUMS`, and
   create the release tag. The install guide tells users to verify against
   `SHA256SUMS` from the Releases page, so it must be there.
5. **Confirm the repository URL** `github.com/zkelder/mockingbird` is the final
   public location (SECURITY.md, issue-template links and troubleshooting use
   it), and **enable GitHub private vulnerability reporting** on that repo
   (SECURITY.md depends on it). If the repository is renamed or moved, update
   those links.
6. **Confirm the maintainer contact path** for security reports works.
7. **Confirm the NVIDIA CUDA/cuDNN redistribution notice** matches what the
   shipped `nvidia-*` packages carry (an open item in
   [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)).
8. **Decide the code-signing position.** Either obtain a certificate and sign,
   or publish unsigned. Docs currently say unsigned (SmartScreen warning,
   checksum verification); change them if you sign.
9. **Confirm the MIT licence holder line** in `LICENSE`
   ("MockingBird contributors") is what you want published.
10. **Decide the BirdNET stance for the release** (never bundled; no supported
    route on the Windows ZIP) and take legal advice before any paid support,
    paid appliance or hosted offering touches the acoustic feature
    (unresolved; recorded in THIRD_PARTY_NOTICES.md).

## Recommended

- Test the release ZIP on **Windows 11** and note the result in the support
  matrix (today: expected, not validated).
- Try one more GPU and record any minimum NVIDIA driver (none is recorded).
- Re-verify that no screenshots or media with private locations are in the
  repository or release (none are committed today).
- Decide where users discuss the project (Issues only today; no forum).
- Dry-run the documented install, verify, first-run, backup and restore path on
  a clean Windows account.

## Optional / post-launch

- A domain and a project website. **None exists**; the repository is the
  public surface.
- Trademark registration for the name (nothing registered or claimed).
- A signing certificate and reproducible-build attestation.
- Contributor-community infrastructure (code of conduct, discussions).
- Packaged Linux Host, macOS, AMD/Apple accelerator validation, native mobile,
  cloud relay and the other post-1.0 items listed in the support matrix.
