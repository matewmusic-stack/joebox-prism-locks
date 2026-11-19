"""Patch JOEBOX 3 test 3.5.zi (BLACKBOX.bin + BBEXTRA.BIN) with the Prism lock targets.

usage: python3 apply.py SRC_DIR OUT_DIR
  SRC_DIR  holds YOUR copy of JOEBOX 3 test 3.5.zi's BLACKBOX.bin and BBEXTRA.BIN (checked by SHA-256)
  OUT_DIR  receives the patched pair. Uses the compiled code in prebuilt/ (rebuild it with src/build.sh).
"""
import hashlib
import os
import struct
import sys

SRC, OUT = sys.argv[1:3]
H = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prebuilt")
B1, B2 = 0x08040000, 0x08100000
b1 = bytearray(open(os.path.join(SRC, "BLACKBOX.bin"), "rb").read())
b2 = bytearray(open(os.path.join(SRC, "BBEXTRA.BIN"), "rb").read())
assert hashlib.sha256(b1).hexdigest() == "657cae3d4dce94b7ef0ee645328e1343ffc5553796c985ab02bdde8498290023"
assert hashlib.sha256(b2).hexdigest() == "890dacec79176f5ffe07fc68e31da80f56cc09ff4884c873acf1936654eaf15a"


def syms(f):
    return {l.split()[2]: int(l.split()[0], 16) for l in open(os.path.join(H, f)) if len(l.split()) == 3}


s1, s2 = syms("b1.sym"), syms("b2.sym")


def branch(at, to, link):
    off = to - (at + 4)
    assert -(1 << 24) <= off < (1 << 24) and off % 2 == 0, hex(off)
    s = 1 if off < 0 else 0
    off &= (1 << 25) - 1
    i1, i2 = (off >> 23) & 1, (off >> 22) & 1
    j1, j2 = (~(i1 ^ s)) & 1, (~(i2 ^ s)) & 1
    hi = 0xF000 | (s << 10) | ((off >> 12) & 0x3FF)
    lo = (0xD000 if link else 0x9000) | (j1 << 13) | (j2 << 11) | ((off >> 1) & 0x7FF)
    return struct.pack("<HH", hi, lo)


bl = lambda at, to: branch(at, to, True)
bw = lambda at, to: branch(at, to, False)
w32 = lambda v: struct.pack("<I", v)
log = []


def patch(img, base, at, old, new):
    o = at - base
    assert img[o:o + len(old)] == old, f"{at:#x}: found {img[o:o + len(old)].hex()} want {old.hex()}"
    img[o:o + len(new)] = new
    log.append(f"{at:#010x}: {old.hex()} -> {new.hex()}")


assert bl(0x08118E30, 0x08118C00) == b2[0x18E30:0x18E34] and bw(0x080FA976, 0x08118634) == b1[0xBA976:0xBA97A]

# ---- bank 2 (BBEXTRA.BIN)
P2 = lambda at, old, new: patch(b2, B2, at, old, new)
P2(0x08118F6E, bytes.fromhex("0d2d"), bytes.fromhex("0f2d"))            # builder: clamp selected target < 15
P2(0x08118FEC, bytes.fromhex("0d2a"), bytes.fromhex("0f2a"))            # builder: 15 names in the list
P2(0x08119384, bytes.fromhex("0c2b"), bytes.fromhex("0e2b"))            # list pick: index <= 14
P2(0x08118FA6, bytes.fromhex("06f54351"), bytes.fromhex("06f54451"))    # name cells: pool+0x311c (ptrs grow to 0x30e0)
P2(0x081190E4, w32(0x08119550), w32(s2["plk_names"]))                  # builder: names table
P2(0x081190F0, w32(0x08119534), w32(s2["plk_pids"]))                   # builder: Amount knob's parameter per target
P2(0x08119054, bytes.fromhex("04eb4504b4f90410"), bl(0x08119054, s2["plk_val_thunk"]) + bytes.fromhex("aff30080"))
P2(0x08119064, bytes.fromhex("0a2d0bd9"), bl(0x08119064, s2["plk_label_thunk"]))
for at in (0x08118E30, 0x081190D4):
    P2(at, bl(at, 0x08118C00), bl(at, s2["plk_base"]))
P2(0x08118DC6, bl(0x08118DC6, 0x081183BA), bl(0x08118DC6, s2["plk_setlock"]))
P2(0x08115C94, bl(0x08115C94, 0x08118496), bl(0x08115C94, s2["plk_fmt"]))
P2(0x08118ED4, w32(0x080B0417), w32(s2["plk_knobval"] | 1))          # Lock Amount knob read: list knobs by index
code2 = open(os.path.join(H, "b2.bin"), "rb").read()
assert len(b2) == 0x1BA00 and s2["plk_intern"] > B2 + len(b2)
b2 += code2
b2 += b"\0" * (-len(b2) % 32)
assert B2 + len(b2) <= 0x081E0000
body = bytes(b2[16:])
chk = sum(struct.unpack(f"<{len(body) // 4}I", body)) & 0xFFFFFFFF
new_id = int(hashlib.sha256(body).hexdigest()[:8], 16)
assert new_id != 0xD5E701D6
b2[0:16] = struct.pack("<IIII", 0x21324242, new_id, len(b2), chk)

# ---- bank 1 (BLACKBOX.bin)
P1 = lambda at, old, new: patch(b1, B1, at, old, new)
P1(0x080FA976, bw(0x080FA976, 0x08118634), bw(0x080FA976, s2["plk_apply"]))   # voice start: lock apply
P1(0x080FA98E, bl(0x080FA98E, 0x08118530), bl(0x080FA98E, s2["plk_parse"]))   # project load: plock attribute
P1(0x080FA9AA, bw(0x080FA9AA, 0x081182D4), bw(0x080FA9AA, s2["plk_reset"]))   # lock pool reset
P1(0x080F97F0, bl(0x080F97F0, 0x080F8E04), bl(0x080F97F0, s1["plk_pct"]))     # Prism: block amounts
P1(0x080F9826, bl(0x080F9826, 0x08093E9C), bl(0x080F9826, s1["plk_time"]))    # Prism: Time
for at in (0x080F1EC8, 0x080F1F0C):
    P1(at, w32(0xD5E701D6), w32(new_id))                                       # bank 2 id this image pairs with
P1(0x080F6524, w32(0x7E5333BE), w32(chk))                                      # bank 2 sum this image expects
code1 = open(os.path.join(H, "b1.bin"), "rb").read()
assert len(b1) == 0xBF820
b1 += code1
b1 += b"\xff" * (-len(b1) % 32)
assert B1 + len(b1) <= 0x08100000

os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "BLACKBOX.bin"), "wb").write(b1)
open(os.path.join(OUT, "BBEXTRA.BIN"), "wb").write(b2)
print("\n".join(log))
print(f"bank 2 id {new_id:#010x}, length {len(b2):#x}, sum {chk:#010x}")
for n, d in (("BLACKBOX.bin", b1), ("BBEXTRA.BIN", b2)):
    print(f"{n}: {len(d)} bytes  sha256 {hashlib.sha256(d).hexdigest()}")
