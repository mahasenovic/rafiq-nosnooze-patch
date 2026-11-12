# Rafiq No-Snooze Patch (unofficial, experimental)

An unofficial, one-instruction patch for the **Rafiq** prayer-times tweak that
makes every prayer alarm Rafiq writes into the iOS Clock app have **Snooze: off**.

**Experimental.** Neither patched package has been installed on a real device
yet. Read "Tested status and limits" and "Before you try" below before using
anything here.

- Rafiq itself is developed by **AnubisTweaks**:
  <https://github.com/AnubisTweaks/AnubisTweaks.github.io>
- This project is **not affiliated with, endorsed by, or connected to the
  developer**. It contains no Rafiq code or assets - only a small script that
  patches a copy of the official package **you download yourself** from the
  developer's own repository.
- If AnubisTweaks ships an official option for this, use that instead and this
  project has done its job.

## What the patch does

Rafiq's daemon (`rafiq-prayerd`) creates/updates the prayer alarms through one
shared helper that ends in a single call:

```objc
[alarm setAllowsSnooze:snooze];   // snooze comes from Rafiq's own setting
```

The patch flips the argument of that one call to `NO` at the machine-code
level:

```
mov x2, x24   ->   mov x2, xzr        bytes: e2 03 18 aa  ->  e2 03 1f aa
```

All other files and the install scripts stay byte-identical to the official
1.4 build. The patcher also repairs the daemon's self-signature after
patching: the official build ships an ldid-style signature (no Apple identity,
private entitlements for alarm access), whose CodeDirectory hashes every code
page; the script re-hashes the one page it changed and verifies every page
hash afterwards, refusing to output anything whose signature does not verify.

One honest caveat about scope: which alarms Rafiq rewrites is decided by
**Rafiq itself** (it looks up its alarms by a stored identifier first, with an
exact-title fallback - stock behavior, unchanged by this patch). An ordinary
alarm you made yourself is only at risk if it shares the exact title of a
Rafiq prayer alarm; in that case Rafiq may treat it as its own, and with the
patch such a rewrite would also force its Snooze off.

## Pick your lane

The developer ships two official builds of Rafiq 1.4. Use the one that matches
your jailbreak, exactly as you would from his repo. These are the *intended*
jailbreak families for each lane - install on any specific environment is not
verified, and this table is not a guaranteed-support list:

| Intended jailbreak family | Official package | Patch lane |
| --- | --- | --- |
| Dopamine (rootless) | `eg.anubistweaks.rafiq_1.4_iphoneos-arm64.deb` | `iphoneos-arm64` |
| Dopamine RootHide / Relaxin / RootHide Bootstrap | `eg.anubistweaks.rafiq_1.4_iphoneos-arm64e.deb` | `iphoneos-arm64e` |

## Build the patched package

You need Python 3 **with the standard `lzma` module** (present in the official
CPython builds for Linux, macOS and Windows). On-device Pythons (a-Shell,
Pythonista) are **untested** - build on a computer and copy the `.deb` over.

```sh
# 1. Download the official package for YOUR lane from the developer's repo:
curl -LO https://raw.githubusercontent.com/AnubisTweaks/AnubisTweaks.github.io/main/debfiles/eg.anubistweaks.rafiq_1.4_iphoneos-arm64.deb
#    (or ..._iphoneos-arm64e.deb for the RootHide family)

# 2. Patch it:
python3 patch_rafiq_nosnooze.py eg.anubistweaks.rafiq_1.4_iphoneos-arm64.deb
#    -> Rafiq-nosnooze-1.4-exp1-iphoneos-arm64.deb
```

The script is fail-closed. It checks the package ID, that the version is
exactly 1.4, the official SHA-256 of the file you downloaded, the exact
original bytes at the patch site, and the daemon's signature before and after
patching. If anything is unexpected it stops and writes nothing.

Expected output SHA-256 (the build is deterministic):

```
iphoneos-arm64:   3da84468ebc89e6115807fadc4eaf82c48d27e97a538299f7a94cda0de4da0f5
iphoneos-arm64e:  b393c1c14dea67b71df59340930012b174a0bf01bb856ea6305da648fd356b56
```

## Before you try

- Both patched packages are **untested as packages** (see below). Try first on
  a device you can afford to experiment on, not your daily driver.
- Back up Rafiq's preferences first, e.g. copy
  `/var/mobile/Library/Preferences/eg.anubistweaks.rafiq*.plist` somewhere
  safe (Filza works).
- Know your way back: keep the official 1.4 `.deb` for your lane at hand.
- The patched build declares version `1.4+local.nosnooze.exp1`, which is
  **higher** than 1.4, so package managers will not automatically offer the
  official 1.4 afterwards; going back means explicitly choosing the official
  1.4 version (that downgrade path is itself untested with this build).

## Install (experimental)

Copy the patched `.deb` to the device and install it with your package manager
or Filza. It has the same package ID as stock Rafiq, so it is an upgrade of
the installed package and uses the developer's own install scripts unchanged -
but note that this exact upgrade path (stock 1.4 -> patched exp1) has not been
run on a real device yet.

Alarms Rafiq has already created keep the state they were last written with.
For existing alarms that still show Snooze on, the reliable fix is manual:
open the alarm in Clock and switch Snooze off once. (Rafiq's own update check
can skip alarms whose times did not change, so there is no dependable way to
make it rewrite every existing alarm on demand.)

## Going back

Reinstalling the official 1.4 package restores the stock code. Two things to
know:

- Alarms already written with Snooze off stay as they are until Rafiq rewrites
  them again; reinstalling stock code does not retroactively change them.
- Removing Rafiq entirely (not just swapping builds) runs the developer's own
  uninstall cleanup, which deletes Rafiq's prayer alarms, the imported azan
  sounds and Rafiq's derived state files. That is stock Rafiq behavior, not something this patch
  adds. A full `purge` also deletes your saved settings.

## Tested status and limits

- **What IS proven on a real device:** the one-instruction code change itself.
  On a Relaxin (RootHide) device running iOS 16.4, a device-specific build
  carrying this change made a rewritten Isha alarm show Snooze off, and it
  stayed off across closing and reopening Clock, while an untouched alarm kept
  its original Snooze setting.
- **What is NOT proven:** the two portable exp1 packages the script
  generates. Neither has been installed on any device. The RootHide-lane device test ran
  a different, device-specific package - same code change, different wrapper.
  The rootless-lane package additionally rests on static analysis only.
- A repaired ad-hoc signature makes the patched daemon exactly as well-signed
  as the official build; it does not by itself prove the daemon will load and
  run on an environment we have not tested. The official install scripts
  (used unchanged) pick the first `.jbroot-*` match and ignore errors, so
  "identical scripts" is not a readiness guarantee for every setup.
- Offsets are specific to Rafiq **1.4**. A future official build needs the
  patch re-verified (the script refuses anything that isn't 1.4).
- The daemon binary itself is plain arm64 in both official builds; the
  `arm64e` lane is a package-manager lane for the RootHide family. Older
  A8-A11 devices on standard Dopamine are not covered by the RootHide lane
  and are untested with the rootless lane.
- Rafiq's own requirement still applies: iOS 15.0+ (`Depends: firmware (>= 15.0)`).

## Files

- `patch_rafiq_nosnooze.py` - the patcher (MIT license, see `LICENSE`)
- `CHANGELOG.md` - complete change record and verification evidence
- `README.md` - this file

If you try a lane on a real device, please open an issue with the result
(device, jailbreak, iOS version, what happened) - that is how these limits
get replaced by facts.

