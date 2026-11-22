#!/usr/bin/env python3
"""Patch libkksdk.so (arm64-v8a) to bypass the Transsion signature gate.

The Kookong IR engine refuses to initialize unless the APK is signed with
Transsion's "welife" certificate (MD5 E83DAE982C78FBDA17F5270720E101AC).

All four native init functions (StreamHelper.init, CodeHelper.init,
StreamHelper2.init, IrDevice.init) call one shared gate routine at
virtual address 0x57ec4. It calls back into Java to compute the signing
cert's MD5, then string-compares it against the expected value.

This script applies three coordinated patches:

  1. gate @ 0x57ec4 : write the Transsion cert MD5 to the out-param and
                      return 1.  Downstream code strcmp()s the out-param
                      against the expected value, so it now matches.
  2. 0x57ad8        : force the "signature matched" branch. This sets the
                      offline decryption-key flag [de000+0xfc] = 1, so the
                      bundled kkoffline.db decrypts with key 0x133a133
                      instead of key 0.
  3. 0x57af4/0x57af8: NOP the free(*out). The out-param now points at a
                      .text string, which must not be freed.

Usage:
    python patch_libkksdk.py path/to/lib/arm64-v8a/libkksdk.so
"""
import struct
import sys

TRANSION_MD5 = "E83DAE982C78FBDA17F5270720E101AC".encode("ascii") + bytes([0])

# The gate replacement: 5 instructions + the null-terminated MD5 string,
# placed at 0x57ec4 (string lands at 0x57ed8).
#   adr x0, +0x14   -> &MD5 string
#   cbz x3, +0x08   -> skip the store if the out-param is NULL
#   str x0, [x3]    -> *out = MD5 string
#   mov w0, #1      -> return success
#   ret
GATE = 0x57EC4
GATE_INSNS = (
    0x100000A0,  # adr x0, #0x14
    0xB4000043,  # cbz x3, #0x8
    0xF9000060,  # str x0, [x3]
    0x52800020,  # mov w0, #1
    0xD65F03C0,  # ret
)

MATCH_BRANCH = 0x57AD8  # b +0xc -> 0x57ae4  (the "matched" path)
FREE_SITE_A = 0x57AF4   # free(*out): mov x0, x20
FREE_SITE_B = 0x57AF8   # free(*out): bl free

NOP = 0xD503201F


def patch(path):
    with open(path, "rb") as f:
        data = bytearray(f.read())

    # 1) gate replacement + embedded MD5 string
    blob = struct.pack("<5I", *GATE_INSNS) + TRANSION_MD5
    data[GATE:GATE + len(blob)] = blob

    # 2) force the matched branch (b +0xc -> 0x57ae4)
    data[MATCH_BRANCH:MATCH_BRANCH + 4] = struct.pack("<I", 0x14000003)

    # 3) NOP the free(*out)
    data[FREE_SITE_A:FREE_SITE_A + 4] = struct.pack("<I", NOP)
    data[FREE_SITE_B:FREE_SITE_B + 4] = struct.pack("<I", NOP)

    with open(path, "wb") as f:
        f.write(data)

    print("patched " + path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python patch_libkksdk.py <libkksdk.so>")
        sys.exit(1)
    patch(sys.argv[1])
