# Changelog - Rafiq No-Snooze Patch (unofficial)

Base: official **Rafiq 1.4** by AnubisTweaks, both package lanes.
Patched builds identify as version **1.4+local.nosnooze.exp1**.

## exp1 - 2026-11-11

### Changed

Exactly two things differ from each official 1.4 package:

1. `usr/local/bin/rafiq-prayerd` (path is under `/var/jb` in the rootless
   lane): one ARM64 instruction at the single `setAllowsSnooze:` call site,
   plus the matching repair of the daemon's self-signature:

   | Lane | Package | File offset | Original bytes | Patched bytes | Meaning |
   | --- | --- | --- | --- | --- | --- |
   | rootless | `iphoneos-arm64` | `0x8460` | `e2 03 18 aa` | `e2 03 1f aa` | `mov x2, x24` -> `mov x2, xzr` |
   | RootHide | `iphoneos-arm64e` | `0x83d8` | `e2 03 18 aa` | `e2 03 1f aa` | `mov x2, x24` -> `mov x2, xzr` |

   Net effect: every prayer alarm Rafiq creates or updates is written with
   `setAllowsSnooze:NO`, so it appears in Clock with Snooze off.

   Signature repair: the official daemon carries an ldid-style self-signature
   (identifier `rafiq-prayerd.964b9cd6.unsigned`, no CMS/Apple identity) with
   private entitlements (`com.apple.private.mobiletimerd`, alarm server
   mach-lookup) and a SHA-256 CodeDirectory over 32 4K code pages. Flipping
   the instruction invalidates the hash of code page 8; the patcher
   re-computes that one hash slot (32 bytes at file offset `0x1f414`) and
   re-verifies all 32 page hashes, so the patched binary is signed to exactly
   the same level as the official build. Requirements blob, entitlements,
   DER entitlements and the special slots are untouched. The patcher refuses
   any input whose own signature does not verify or that carries a real CMS
   identity.

2. `DEBIAN/control`: `Version: 1.4` -> `Version: 1.4+local.nosnooze.exp1`
   so package managers can tell the patched build apart from stock.

### NOT changed

- All other 203 payload files (bundle resources, azan audio, fonts,
  preference bundle, widget/Qibla dylibs, `rafiq-tones`, launch plist):
  byte-identical to the official packages.
- `postinst` and `prerm`: byte-identical to the official scripts (they
  already resolve the install root dynamically for both environments).
- File modes, ownership (root:root), sizes and tar layout.
- Package ID, dependencies (`mobilesubstrate, preferenceloader,
  firmware (>= 15.0)`), section, author fields.

### Verification evidence (reproducible)

- Official inputs, verified against the developer's own Packages index
  (<https://raw.githubusercontent.com/AnubisTweaks/AnubisTweaks.github.io/main/Packages>):
  - `eg.anubistweaks.rafiq_1.4_iphoneos-arm64.deb`
    SHA-256 `2b917ea5015c9b1bad44aab39616469f7a88a782adfb00b8bf5419b41d092a10`
  - `eg.anubistweaks.rafiq_1.4_iphoneos-arm64e.deb`
    SHA-256 `d8a01573609b462cae3d3230a9d03db5a8a01b091b3ceabf298c6a93f5f4e252`
- Patch-site analysis, done independently for each lane: the string
  `setAllowsSnooze:` has exactly one selector reference in each daemon, and
  exactly one code reference to it in `__text` (an `ldr x1, =selref`
  immediately followed by `mov x0, x19; mov x2, x24; bl <objc_msgSend
  thunk>`), so the patched instruction feeds the only snooze write.
- Recursive SHA-256 comparison of the extracted patched package against the
  extracted official package: only `rafiq-prayerd` (the instruction byte plus
  the 32-byte repaired page-hash slot) and the `Version` line differ.
- Signature verification of the patched daemon: all 32 code-page hashes
  verify against the patched bytes; special slots, requirements, entitlements
  and DER entitlements are byte-identical to official; no CMS identity.
- Tar member metadata (names, modes, owners, sizes) identical to official.
- The patched packages are deterministic output of
  `patch_rafiq_nosnooze.py`; expected SHA-256:
  - `Rafiq-nosnooze-1.4-exp1-iphoneos-arm64.deb`
    `3da84468ebc89e6115807fadc4eaf82c48d27e97a538299f7a94cda0de4da0f5`
  - `Rafiq-nosnooze-1.4-exp1-iphoneos-arm64e.deb`
    `b393c1c14dea67b71df59340930012b174a0bf01bb856ea6305da648fd356b56`

### Tested status

- **Proven on a real device:** the one-instruction code change itself, via a
  separate device-specific build on a Relaxin (RootHide) device, iOS 16.4.
  Test: change the Isha time, tap Calculate -> the rewritten Isha alarm shows
  Snooze off, and it stays off after closing and reopening Clock. An
  untouched alarm kept Snooze on, confirming the change only affects alarms
  Rafiq rewrites.
- **NOT proven:** the two portable exp1 packages produced by the patcher.
  Neither has been installed on any device; the stock 1.4 -> exp1 upgrade
  path, the per-environment install conversion, and the
  exp1 -> official 1.4 downgrade path are all untested. The rootless-lane
  build additionally rests on static analysis only. A repaired ad-hoc
  signature matches the official build's signing level but does not by itself
  establish that the daemon loads on an untested environment, and the stock
  scripts' error-ignoring, first-glob jbroot resolution is not a readiness
  guarantee.

### Known limits

- Offsets are valid for Rafiq 1.4 only; the patcher refuses other versions.
- Existing alarms keep the state they were last written with; Rafiq's update
  check may skip alarms whose times did not change, so there is no dependable
  on-demand rewrite. The reliable fix for an existing alarm that still shows
  Snooze is to switch it off manually in Clock once.
- Rafiq decides which alarms it manages (stored identifier first, exact-title
  fallback - stock behavior). An ordinary alarm sharing a prayer alarm's
  exact title can be treated as Rafiq's; with the patch, such a rewrite also
  forces its Snooze off.
- A8-A11 devices: not covered by the RootHide lane; untested with the
  rootless lane.
- The patcher requires Python 3 with the standard `lzma` module; on-device
  Python environments (a-Shell, Pythonista) are untested.
- No overnight/reboot persistence testing beyond the checks above.

### Recovery

Reinstalling the official 1.4 package for your lane restores the stock code.
Caveats: exp1 declares a higher version, so package managers will not offer
the official 1.4 automatically - the downgrade must be chosen explicitly and
is untested with this build; alarms already written with Snooze off keep
their state until Rafiq rewrites them; and removing Rafiq entirely runs the
developer's own cleanup, which deletes Rafiq's prayer alarms, the imported
azan sounds and derived state files (a full `purge` also deletes saved
settings) - that is stock
behavior, unchanged by this patch. Back up
`/var/mobile/Library/Preferences/eg.anubistweaks.rafiq*.plist` before
experimenting.

### Sources

Note: the lane table names the *intended* jailbreak family per lane. Install
on any specific environment (Dopamine, RootHide, Relaxin, RootHide Bootstrap)
is not verified by the packages' authors; the sources below are general
references, not a guaranteed-support list.

- Official packages + index:
  <https://raw.githubusercontent.com/AnubisTweaks/AnubisTweaks.github.io/main/Packages>
  <https://github.com/AnubisTweaks/AnubisTweaks.github.io>
- Dopamine support ranges:
  <https://raw.githubusercontent.com/opa334/Dopamine/3.x/README.md>
  <https://ellekit.space/dopamine/>
- RootHide lane note (arm64e packaging lane):
  <https://github.com/roothide/Dopamine2-roothide/issues/61>
