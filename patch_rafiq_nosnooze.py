#!/usr/bin/env python3
"""
patch_rafiq_nosnooze.py - build a no-snooze variant of the official Rafiq 1.4 package.

Unofficial patch, not affiliated with or endorsed by AnubisTweaks.
Rafiq itself is (c) AnubisTweaks: https://github.com/AnubisTweaks/AnubisTweaks.github.io

What it does
------------
Takes an OFFICIAL Rafiq 1.4 .deb (either lane: iphoneos-arm64 for Dopamine
rootless, iphoneos-arm64e for the RootHide family), flips exactly one ARM64
instruction inside the rafiq-prayerd daemon:

    mov x2, x24   ->   mov x2, xzr        (bytes e20318aa -> e2031faa)

That instruction is the argument of the single setAllowsSnooze: call the
daemon makes when it writes a prayer alarm into the Clock app, so every
alarm Rafiq creates or updates gets "Snooze: off". Nothing else in the
package is touched (the control Version field is bumped to
1.4+local.nosnooze.exp1 so the package manager can tell the builds apart).

The script is fail-closed: it verifies the official package SHA-256, the
package version, the exact original bytes at the patch site and the lane,
and refuses to produce output if anything is unexpected.

Usage
-----
    python3 patch_rafiq_nosnooze.py <official.deb> [output.deb]

Download the official packages from the developer's own repository:
    https://raw.githubusercontent.com/AnubisTweaks/AnubisTweaks.github.io/main/debfiles/eg.anubistweaks.rafiq_1.4_iphoneos-arm64.deb
    https://raw.githubusercontent.com/AnubisTweaks/AnubisTweaks.github.io/main/debfiles/eg.anubistweaks.rafiq_1.4_iphoneos-arm64e.deb

Pure Python 3 standard library - no dependencies. Works on Linux, macOS,
or on-device in a Python environment (a-Shell, Pythonista, ...).
"""

import io
import sys
import gzip
import lzma
import hashlib
import tarfile

PATCH_FROM = bytes.fromhex("e20318aa")  # mov x2, x24
PATCH_TO   = bytes.fromhex("e2031faa")  # mov x2, xzr
EXPECTED_VERSION = "1.4"
NEW_VERSION = "1.4+local.nosnooze.exp1"

import struct


def codesign_repair(original, patched, patch_off):
    """The official daemon ships an ldid-style self-signature (no CMS
    identity) whose CodeDirectory holds a SHA-256 per 4K code page. Patching
    one byte invalidates exactly one page hash. This verifies the original
    signature is complete and self-consistent, then repairs the one page
    hash so the patched binary is signed to exactly the same level as the
    official build. Fails closed on anything unexpected (real CMS identity,
    unknown hash type, or any page hash that does not verify)."""
    def parse(d):
        n = struct.unpack_from("<I", d, 16)[0]
        o = 32
        cs = None
        for _ in range(n):
            cmd, size = struct.unpack_from("<II", d, o)
            if cmd == 0x1D:  # LC_CODE_SIGNATURE
                cs = struct.unpack_from("<II", d, o + 8)
            o += size
        if cs is None:
            fail("daemon has no LC_CODE_SIGNATURE - unexpected for the official build")
        soff = cs[0]
        if struct.unpack_from(">I", d, soff)[0] != 0xFADE0CC0:
            fail("unexpected signature superblob magic")
        cnt = struct.unpack_from(">I", d, soff + 8)[0]
        blobs = {}
        for i in range(cnt):
            typ, boff = struct.unpack_from(">II", d, soff + 12 + 8 * i)
            blobs[typ] = soff + boff
        return blobs

    blobs = parse(original)
    if 0x1000 in blobs:
        fail("daemon carries a real CMS code signature - refusing to touch it")
    cd = blobs.get(0x0)
    if cd is None:
        fail("no primary CodeDirectory in signature")
    if struct.unpack_from(">I", original, cd)[0] != 0xFADE0C02:
        fail("unexpected CodeDirectory magic")
    _, _, _, _, hash_off, _, _, n_code, code_limit = struct.unpack_from(">9I", original, cd)
    hash_size, hash_type, _, page_shift = struct.unpack_from(">4B", original, cd + 36)
    if hash_type not in (1, 2):
        fail(f"unsupported CodeDirectory hash type {hash_type}")
    hfn = hashlib.sha1 if hash_type == 1 else hashlib.sha256
    if hfn().digest_size != hash_size:
        fail("CodeDirectory hash size does not match its hash type")
    page = 1 << page_shift
    h0 = cd + hash_off

    def verify_all(d):
        bad = [p for p in range(n_code)
               if hfn(d[p * page:min((p + 1) * page, code_limit)]).digest()
               != d[h0 + p * hash_size:h0 + (p + 1) * hash_size]]
        return bad

    if verify_all(original):
        fail("the official daemon's own code-page hashes do not verify - unexpected input")
    if patch_off >= code_limit:
        fail("patch site lies outside the signed code range - refusing to guess")
    out = bytearray(patched)
    p = patch_off // page
    out[h0 + p * hash_size:h0 + (p + 1) * hash_size] = \
        hfn(bytes(out[p * page:min((p + 1) * page, code_limit)])).digest()
    bad = verify_all(bytes(out))
    if bad:
        fail(f"internal error: signature repair failed on page(s) {bad}")
    return bytes(out)

# Verified against the developer's own Packages index
# (https://raw.githubusercontent.com/AnubisTweaks/AnubisTweaks.github.io/main/Packages)
LANES = {
    "iphoneos-arm64": {   # Dopamine rootless lane
        "sha256": "2b917ea5015c9b1bad44aab39616469f7a88a782adfb00b8bf5419b41d092a10",
        "offset": 0x8460,
    },
    "iphoneos-arm64e": {  # RootHide family lane (Dopamine RootHide, Relaxin, ...)
        "sha256": "d8a01573609b462cae3d3230a9d03db5a8a01b091b3ceabf298c6a93f5f4e252",
        "offset": 0x83D8,
    },
}


def fail(msg):
    sys.exit(f"error: {msg}")


def ar_read(raw):
    if raw[:8] != b"!<arch>\n":
        fail("not an ar archive (not a .deb?)")
    members = []
    off = 8
    while off < len(raw):
        hdr = raw[off:off + 60]
        off += 60
        name = hdr[0:16].decode().strip().rstrip("/")
        size = int(hdr[48:58].decode().strip())
        members.append((name, raw[off:off + size]))
        off += size + (size % 2)
    return members


def ar_write(path, members):
    out = bytearray(b"!<arch>\n")
    for name, body in members:
        hdr = f"{name + '/':<16}{0:<12}{0:<6}{0:<6}{0o100644:<8o}{len(body):<10}`\n"
        out += hdr.encode() + body
        if len(body) % 2:
            out += b"\n"
    with open(path, "wb") as f:
        f.write(bytes(out))


def tar_rewrite(raw, replace):
    """Copy a tar byte-for-byte in metadata terms, swapping member contents
    named in replace {name: bytes}. Preserves order, modes, owners, mtimes."""
    src = tarfile.open(fileobj=io.BytesIO(raw), mode="r:")
    buf = io.BytesIO()
    dst = tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT)
    seen = set()
    for m in src.getmembers():
        if m.name in seen:
            fail(f"duplicate tar member {m.name}")
        seen.add(m.name)
        if m.isfile():
            data = replace.get(m.name)
            if data is None:
                data = src.extractfile(m).read()
            m.size = len(data)
            dst.addfile(m, io.BytesIO(data))
        else:
            dst.addfile(m)
    dst.close()
    missing = set(replace) - seen
    if missing:
        fail(f"expected member(s) not found in tar: {sorted(missing)}")
    return buf.getvalue()


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: python3 patch_rafiq_nosnooze.py <official.deb> [output.deb]")
    src_path = sys.argv[1]
    raw = open(src_path, "rb").read()

    members = dict(ar_read(raw))
    for need in ("debian-binary", "control.tar.gz", "data.tar.lzma"):
        if need not in members:
            fail(f"{need} missing - this does not look like the official Rafiq package")

    # --- identify the lane from the control file --------------------------
    ctl_raw = gzip.decompress(members["control.tar.gz"])
    ctl_tar = tarfile.open(fileobj=io.BytesIO(ctl_raw), mode="r:")
    control = None
    scripts = {}
    for m in ctl_tar.getmembers():
        body = ctl_tar.extractfile(m).read() if m.isfile() else None
        name = m.name.lstrip("./")
        if name == "control":
            control = body.decode()
        elif body is not None:
            scripts[name] = body
    if control is None:
        fail("no control file in control.tar.gz")

    fields = {}
    for line in control.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            fields[k] = v
    if fields.get("Package") != "eg.anubistweaks.rafiq":
        fail(f"unexpected package id: {fields.get('Package')!r} (this script only patches Rafiq)")
    if fields.get("Version") != EXPECTED_VERSION:
        fail(f"unexpected Rafiq version {fields.get('Version')!r}: the patch offsets are "
             f"verified for {EXPECTED_VERSION} only. Check the project page for an updated patch.")
    arch = fields.get("Architecture")
    if arch not in LANES:
        fail(f"unexpected Architecture {arch!r}; expected one of {sorted(LANES)}")
    lane = LANES[arch]

    digest = hashlib.sha256(raw).hexdigest()
    if digest != lane["sha256"]:
        fail(f"SHA-256 mismatch for the official {arch} package.\n"
             f"  expected {lane['sha256']}\n  got      {digest}\n"
             f"Download the untouched official deb from the AnubisTweaks repo (see header).")

    # --- patch the daemon inside data.tar.lzma ----------------------------
    data_raw = lzma.decompress(members["data.tar.lzma"])
    daemon_name = None
    with tarfile.open(fileobj=io.BytesIO(data_raw), mode="r:") as t:
        for m in t.getmembers():
            if m.name.endswith("usr/local/bin/rafiq-prayerd"):
                if daemon_name is not None:
                    fail("more than one rafiq-prayerd member?")
                daemon_name = m.name
    if daemon_name is None:
        fail("rafiq-prayerd not found in data.tar")

    with tarfile.open(fileobj=io.BytesIO(data_raw), mode="r:") as t:
        daemon = t.extractfile(daemon_name).read()
    off = lane["offset"]
    if daemon[off:off + 4] != PATCH_FROM:
        fail(f"unexpected bytes at the patch site (file offset {off:#x}): "
             f"{daemon[off:off+4].hex()}, expected {PATCH_FROM.hex()}. Wrong build?")
    patched = codesign_repair(daemon, daemon[:off] + PATCH_TO + daemon[off + 4:], off)
    assert sum(a != b for a, b in zip(daemon, patched)) >= 1

    new_data = tar_rewrite(data_raw, {daemon_name: patched})
    new_data_lzma = lzma.compress(new_data, format=lzma.FORMAT_ALONE, preset=6)

    # --- bump Version in control ------------------------------------------
    if f"\nVersion: {EXPECTED_VERSION}\n" not in control:
        fail("could not locate the Version line in control")
    new_control = control.replace(f"\nVersion: {EXPECTED_VERSION}\n",
                                  f"\nVersion: {NEW_VERSION}\n")
    ctl_replace = {}
    for m in tarfile.open(fileobj=io.BytesIO(ctl_raw), mode="r:").getmembers():
        if m.name.lstrip("./") == "control":
            ctl_replace[m.name] = new_control.encode()
    new_ctl = gzip.compress(tar_rewrite(ctl_raw, ctl_replace), mtime=0)

    # --- write the new deb --------------------------------------------------
    out_path = sys.argv[2] if len(sys.argv) == 3 else \
        f"Rafiq-nosnooze-{EXPECTED_VERSION}-exp1-{arch}.deb"
    ar_write(out_path, [("debian-binary", members["debian-binary"]),
                        ("control.tar.gz", new_ctl),
                        ("data.tar.lzma", new_data_lzma)])

    print(f"lane:           {arch}")
    print(f"patched:        {daemon_name} @ {off:#x}: {PATCH_FROM.hex()} -> {PATCH_TO.hex()}")
    print(f"version:        {EXPECTED_VERSION} -> {NEW_VERSION}")
    print(f"wrote:          {out_path}")
    print(f"output SHA-256: {hashlib.sha256(open(out_path, 'rb').read()).hexdigest()}")
    print("OK - one instruction changed, everything else byte-identical to the official package.")


if __name__ == "__main__":
    main()
