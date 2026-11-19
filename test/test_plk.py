"""usage: python3 test/test_plk.py PATCHED_DIR ORIGINAL_DIR   (needs: pip install unicorn capstone)

Prism lock targets under Unicorn, on the patched BLACKBOX.bin + BBEXTRA.BIN (and the originals, for comparison).

Real code run: plk_intern / plk_setlock / plk_fmt / plk_parse / plk_base / plk_apply / plk_reset, the JOEBOX originals
they replace (0x08118322, 0x081183ba, 0x08118496, 0x08118530), JOEBOX's pool init and record lookup, the stock
settings read, the bank 1 Prism readers (plk_pct / plk_time) and JOEBOX's pct, the two builder thunks in place,
and the patched name-list loop of JOEBOX's Lock page builder (0x08118fa2 .. 0x08118ff4).
Stubbed: the XML attribute read (returns a given string), JOEBOX's apply (recorded), JOEBOX's base for targets
0..12 (recorded), the lock-pool getter in bank 1 (0x080fa914, returns the test pool).
"""
import random
import struct
import sys

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_THUMB, Uc
from unicorn.arm_const import *

NEW, OLD = sys.argv[1:3]
B1, B2 = 0x08040000, 0x08100000
RET = 0x08000100
STACK = 0x2001F000
SETTINGS, ENTRIES = 0x24028D18, 0x24060000
POOL_A, POOL_B = 0x24100000, 0x24110000
EV, STR, TMP = 0x24120000, 0x24121000, 0x24122000


def syms(f):
    return {l.split()[2]: int(l.split()[0], 16) for l in open(f) if len(l.split()) == 3}


import os
PRE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prebuilt")
s1, s2 = syms(os.path.join(PRE, "b1.sym")), syms(os.path.join(PRE, "b2.sym"))


class M:
    def __init__(self, d):
        self.uc = uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        uc.ctl_set_cpu_model(UC_CPU_ARM_MAX)
        uc.mem_map(0x08000000, 0x200000)
        uc.mem_write(B1, open(f"{d}/BLACKBOX.bin", "rb").read())
        uc.mem_write(B2, open(f"{d}/BBEXTRA.BIN", "rb").read())
        uc.mem_write(RET, b"\x00\xbf\x00\xbf")
        uc.mem_map(0x24000000, 0x200000)
        uc.mem_map(0x20000000, 0x20000)
        uc.reg_write(UC_ARM_REG_C1_C0_2, 0xF << 20)
        uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
        self.stubs = {}
        uc.hook_add(UC_HOOK_CODE, self._hook)
        self.log = []

    def _hook(self, uc, a, size, _):
        f = self.stubs.get(a)
        if f:
            r = f()
            if r is not None:
                uc.reg_write(UC_ARM_REG_R0, r & 0xFFFFFFFF)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def call(self, fn, *args, stack=()):
        uc = self.uc
        regs = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
        for r, v in zip(regs, args):
            uc.reg_write(r, v & 0xFFFFFFFF)
        uc.mem_write(STACK, b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in stack) + bytes(16))
        uc.reg_write(UC_ARM_REG_SP, STACK)
        uc.reg_write(UC_ARM_REG_LR, RET | 1)
        uc.emu_start(fn | 1, RET, count=2_000_000)
        assert uc.reg_read(UC_ARM_REG_PC) == RET, hex(uc.reg_read(UC_ARM_REG_PC))
        return uc.reg_read(UC_ARM_REG_R0)

    def rd(self, a, n): return bytes(self.uc.mem_read(a, n))
    def wr(self, a, b): self.uc.mem_write(a, b)
    def r16(self, a): return struct.unpack("<h", self.rd(a, 2))[0]
    def r32(self, a): return struct.unpack("<I", self.rd(a, 4))[0]
    def w32(self, a, v): self.wr(a, struct.pack("<I", v & 0xFFFFFFFF))

    def cstr(self, a):
        s = b""
        while (c := self.rd(a, 1)) != b"\0":
            s += c
            a += 1
        return s.decode()


new, old = M(NEW), M(OLD)
fails = 0


def check(label, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + label + ("" if ok else f"  [{detail}]"))
    fails += not ok


def store(m, entries):
    m.wr(SETTINGS, bytes(16))
    m.w32(SETTINGS + 4, ENTRIES)
    m.wr(SETTINGS + 0xA, struct.pack("<HH", len(entries), 0x70))
    m.wr(ENTRIES, bytes(0x70 * 8))
    for i, (p, v) in enumerate(entries):
        m.wr(ENTRIES + i * 8, struct.pack("<HHi", p, 0, v))


XML = {"s": ""}
for m in (new, old):
    def xml(m=m):
        m.wr(STR, XML["s"].encode() + b"\0")
        return STR
    m.stubs[0x0804A66C] = xml

POOL_FN, LOOKUP = 0x0811825C, 0x081182EE
O_SETLOCK, O_FMT, O_PARSE, O_INTERN = 0x081183BA, 0x08118496, 0x08118530, 0x08118322


def fresh(m, P):
    m.wr(P, bytes(0x3200))
    m.call(POOL_FN, P)


# ---------------------------------------------------------------- 1. same behaviour as JOEBOX for targets 0..12
random.seed(7)
fresh(new, POOL_A)
fresh(old, POOL_A)
ids_new, ids_old, same = [0] * 8, [0] * 8, True
for step in range(600):
    note = random.randrange(8)
    bit = random.randrange(13)
    val = random.choice([0, 1, 7, 500, 1000, -24, 24, random.randrange(-999, 1000)])
    clear = random.random() < 0.25
    who = random.choice([0x11, 0x22])
    a = new.call(s2["plk_setlock"], POOL_A, ids_new[note], who, bit, stack=(val, clear))
    b = old.call(O_SETLOCK, POOL_A, ids_old[note], who, bit, stack=(val, clear))
    ids_new[note], ids_old[note] = a, b
    if a != b or new.rd(POOL_A, 0x2020) != old.rd(POOL_A, 0x2020):
        same = False
        print("  diverged at step", step, hex(a), hex(b))
        break
check("600 random lock edits on targets 0-12: same ids and same pool bytes as JOEBOX", same)

ok = True
for note in range(8):
    if not ids_new[note]:
        continue
    new.call(s2["plk_fmt"], POOL_A, ids_new[note], TMP)
    old.call(O_FMT, POOL_A, ids_old[note], TMP)
    a, b = new.cstr(TMP), old.cstr(TMP)
    if a != b:
        ok = False
        print("  fmt", a, "vs", b)
check("save text identical to JOEBOX's for targets 0-12", ok)

ok = True
for note in range(8):
    if not ids_new[note]:
        continue
    new.call(s2["plk_fmt"], POOL_A, ids_new[note], TMP)
    XML["s"] = new.cstr(TMP)
    new.wr(EV, bytes([1]) + bytes(0x1F))
    old.wr(EV, bytes([1]) + bytes(0x1F))
    new.call(s2["plk_parse"], POOL_A, 0x1234, EV)
    old.call(O_PARSE, POOL_A, 0x1234, EV)
    if new.r32(EV + 0x14) != old.r32(EV + 0x14) or new.r32(EV + 0x14) != ids_new[note]:
        ok = False
        print("  parse", XML["s"], hex(new.r32(EV + 0x14)), hex(old.r32(EV + 0x14)), hex(ids_new[note]))
check("load of saved text: same record id as JOEBOX (dedupes to the saved record)", ok)

ok = True
for txt in ["", "q:5", "0:12,zz", "1:-7,f:300", "0:123456", "x", "0:5,", ":1", "n:1000,s:0,l:55"]:
    XML["s"] = txt
    new.wr(EV, bytes([1]) + bytes(0x13) + b"\xaa" * 4)
    old.wr(EV, bytes([1]) + bytes(0x13) + b"\xaa" * 4)
    new.call(s2["plk_parse"], POOL_A, 0x1234, EV)
    old.call(O_PARSE, POOL_A, 0x1234, EV)
    if new.r32(EV + 0x14) != old.r32(EV + 0x14):
        ok = False
        print("  parse odd", repr(txt), hex(new.r32(EV + 0x14)), hex(old.r32(EV + 0x14)))
check("odd / damaged plock text parses to the same result as JOEBOX", ok, "")
check("pool bytes still identical after all loads", new.rd(POOL_A, 0x2020) == old.rd(POOL_A, 0x2020))

# ---------------------------------------------------------------- 2. the two Prism targets
P = POOL_B
fresh(new, P)
idv = new.call(s2["plk_setlock"], P, 0, 0x11, 0, stack=(12, 0))
idv = new.call(s2["plk_setlock"], P, idv, 0x11, 13, stack=(735, 0))
idv = new.call(s2["plk_setlock"], P, idv, 0x11, 14, stack=(5, 0))
rec = new.call(LOOKUP, P, idv)
check("record: mask has bits 0, 13, 14", rec and struct.unpack("<H", new.rd(rec, 2))[0] == 0x6001, hex(rec))
check("record: Space 735 at +30, Time 5 at +2, Pitch 12 at +4",
      (new.r16(rec + 30), new.r16(rec + 2), new.r16(rec + 4)) == (735, 5, 12))
new.call(s2["plk_fmt"], P, idv, TMP)
txt = new.cstr(TMP)
check('save text "0:12,x:735,t:5"', txt == "0:12,x:735,t:5", txt)
XML["s"] = txt
new.wr(EV, bytes([1]) + bytes(0x1F))
new.call(s2["plk_parse"], P, 0x1234, EV)
check("load gives back the same record", new.r32(EV + 0x14) == idv, hex(new.r32(EV + 0x14)))
old_P = 0x24130000
fresh(old, old_P)
old.wr(EV, bytes([1]) + bytes(0x1F))
old.call(O_PARSE, old_P, 0x1234, EV)
orec = old.call(LOOKUP, old_P, old.r32(EV + 0x14))
check("original JOEBOX loading this text keeps Pitch and ignores x / t (projects stay loadable)",
      orec and struct.unpack("<H", old.rd(orec, 2))[0] == 1 and old.r16(orec + 4) == 12)
idv2 = new.call(s2["plk_setlock"], P, idv, 0x11, 13, stack=(0, 1))
rec2 = new.call(LOOKUP, P, idv2)
check("clearing PrSpace leaves Pitch and PrTime", struct.unpack("<H", new.rd(rec2, 2))[0] == 0x4001 and new.r16(rec2 + 2) == 5)
# a long lock still fits the 120-byte save buffer
idl = 0
for b in range(15):
    idl = new.call(s2["plk_setlock"], P, idl, 0x33, b, stack=(-12345 if b < 13 else (1000 if b == 13 else 7), 0))
new.wr(TMP, b"\xee" * 200)
new.call(s2["plk_fmt"], P, idl, TMP)
L = len(new.cstr(TMP))
check(f"worst-case save text stays inside the 120-byte buffer ({L} chars)", L <= 118 and new.rd(TMP + 120, 4) == b"\xee" * 4)

# base: Prism targets read the Prism settings; 0..12 go to JOEBOX
store(new, [(0x1A3, 420), (0x1A7, 6)])
base_calls = []
new.stubs[0x08118C00] = lambda: (base_calls.append(new.uc.reg_read(UC_ARM_REG_R2)), 99)[1]
r13 = new.call(s2["plk_base"], P, EV, 13)
r14 = new.call(s2["plk_base"], P, EV, 14)
r3 = new.call(s2["plk_base"], P, EV, 3)
check("unlocked value: PrSpace = Prism Space knob, PrTime = Prism Time knob", (r13, r14) == (420, 6))
check("unlocked value of targets 0-12 still JOEBOX's", r3 == 99 and base_calls == [3])
del new.stubs[0x08118C00]

# apply: override set by a locked note, cleared by the same pad's unlocked note
applied = []
new.stubs[0x08118634] = lambda: applied.append(tuple(new.uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)))
new.stubs[0x080FA914] = lambda: P
OVR = P + 0x31C0
PAD_A, PAD_B = 0x24070000, 0x24071000


def note(pad, lock_id):
    new.w32(P + 8, lock_id)
    new.w32(P + 0xC, pad if lock_id else 0)
    new.call(s2["plk_apply"], P, 0x24072000, pad, 1)


def prism():
    s = new.call(s1["plk_pct"], 0x1A3)
    sp = struct.unpack("<f", struct.pack("<I", new.uc.reg_read(UC_ARM_REG_S0)))[0]
    t = new.call(s1["plk_time"], SETTINGS, 0x1A7)
    return round(sp, 4), t


def mk(who, items):
    i = 0
    for b, v in items:
        i = new.call(s2["plk_setlock"], P, i, who, b, stack=(v, 0))
    return i


idv = mk(0x44, [(0, 12), (13, 735), (14, 5)])
new.wr(OVR, bytes(20))
check("no lock yet: Prism reads its knobs (42 %, Time 6)", prism() == (0.42, 6), prism())
note(PAD_A, idv)
check("JOEBOX's own apply still runs, with the same arguments", applied[-1] == (P, 0x24072000, PAD_A, 1))
check("locked note on pad A: Prism Space 73.5 %, Time 1/4D (5)", prism() == (0.735, 5), prism())
note(PAD_B, 0)
check("pad B plays unlocked: lock on Prism stays", prism() == (0.735, 5), prism())
id_t = new.call(s2["plk_setlock"], P, 0, 0x11, 14, stack=(1, 0))
note(PAD_A, id_t)
check("pad A note with only PrTime 1/16: Time 1, Space back to the knob", prism() == (0.42, 1), prism())
note(PAD_A, 0)
check("pad A unlocked note: both back to the knobs", prism() == (0.42, 6), prism())
note(PAD_A, idv)
new.w32(P + 0xC, PAD_B)                       # a pending id that belongs to another pad is not ours
new.call(s2["plk_apply"], P, 0x24072000, PAD_A, 0)
check("a pending lock for another pad does not count (pad A reverts)", prism() == (0.42, 6), prism())
note(PAD_A, idv)
new.call(s2["plk_reset"], P)
check("lock pool reset (project load) drops the override", prism() == (0.42, 6), prism())
new.stubs[0x080FA914] = lambda: 0
note(PAD_A, idv)
check("bank 2 not live: Prism reads the knobs and never touches bank 2", prism() == (0.42, 6), prism())

# ---------------------------------------------------------------- 3. the patched builder
idv = mk(0x55, [(0, 12), (13, 735), (14, 5)])
rec = new.call(LOOKUP, P, idv)
for sel, want in ((13, 735), (14, 5), (0, 12), (3, 0)):
    u = new.uc
    u.reg_write(UC_ARM_REG_R4, rec)
    u.reg_write(UC_ARM_REG_R5, sel)
    u.reg_write(UC_ARM_REG_R2, 0x77)
    u.reg_write(UC_ARM_REG_R0, 0x66)
    u.reg_write(UC_ARM_REG_SP, STACK)
    u.emu_start(0x08119054 | 1, 0x0811905C, count=100)
    v = struct.unpack("<i", struct.pack("<I", u.reg_read(UC_ARM_REG_R1)))[0]
    check(f"builder: selected target {sel} shows value {want}", v == want and u.reg_read(UC_ARM_REG_R2) == 0x77 and u.reg_read(UC_ARM_REG_R0) == 0x66, v)
for sel, special in ((0, False), (10, False), (11, True), (12, True), (13, False), (14, False)):
    u = new.uc
    u.reg_write(UC_ARM_REG_R5, sel)
    u.reg_write(UC_ARM_REG_SP, STACK)
    hit = []
    h = u.hook_add(UC_HOOK_CODE, lambda uc, a, s, _: (hit.append(a), uc.emu_stop()), begin=0x08119068, end=0x08119068)
    h2 = u.hook_add(UC_HOOK_CODE, lambda uc, a, s, _: (hit.append(a), uc.emu_stop()), begin=0x08119080, end=0x08119080)
    u.emu_start(0x08119064 | 1, 0, count=50)
    u.hook_del(h)
    u.hook_del(h2)
    check(f"builder: target {sel} {'gets' if special else 'skips'} the Start/Length label", hit and (hit[0] == 0x08119068) == special, [hex(x) for x in hit])

# name list: run JOEBOX's loop with the patched constants, name table and cell base
u = new.uc
UI = P
new.wr(UI + 0x3000, bytes(0x200))
rec = new.call(LOOKUP, P, idv)
u.reg_write(UC_ARM_REG_R4, rec)
u.reg_write(UC_ARM_REG_R6, UI)
u.reg_write(UC_ARM_REG_SP, STACK)
u.emu_start(0x08118FA2 | 1, 0x08118FF6, count=5000)
n = struct.unpack("<I", new.rd(STACK + 8, 4))[0]
names = [new.cstr(new.r32(UI + 0x30A8 + 4 * i)) for i in range(15)]
check("Lock target list has 15 entries", n == 15, n)
check("list: '*' on Pitch, PrSpace, PrTime (the targets this note locks)",
      names == ["*Pitch", "Filter", "Res", "Attack", "Decay", "Sustain", "Release", "FX1", "FX2", "Level", "Pan",
                "Start", "Length", "*PrSpace", "*PrTime"], names)
cells = [new.r32(UI + 0x30A8 + 4 * i) for i in range(15)]
check("name cells (pool+0x311c..) clear of the pointer list and inside the pool",
      min(cells) >= UI + 0x30A8 + 60 and max(cells) + 9 <= UI + 0x31C0, (hex(min(cells)), hex(max(cells))))

# ---------------------------------------------------------------- 4. the Lock Amount knob read (PrTime fix)
K = 0x24140000
new.wr(K, bytes(0x400))
new.wr(K + 0x31, bytes([5]))                       # list knob, as bound to Prism Time
new.w32(K + 0x154, 8)                             # 8 entries
new.w32(K + 0x158, 0x24141000)
new.wr(0x24141000, b"".join(struct.pack("<I", 0x081194A9) for _ in range(8)))
new.stubs[0x080B0480] = lambda: 0                 # knob redraw
new.stubs[0x080C3B98] = lambda: 0                 # label text
new.call(0x080B08F4, K, 3, 1)                     # stock set-value, as the bind does (index 3 = 1/8)
v34 = new.r32(K + 0x34)
before_old = new.call(0x080B0416, K, v34)
before_new = new.call(s2["plk_knobval"], K, v34)
new.call(0x080B08F4, K, 6, 0)                     # stock set-value, as a turn does (to 1/4D)
v34b = new.r32(K + 0x34)
after_old = new.call(0x080B0416, K, v34b)
after_new = new.call(s2["plk_knobval"], K, v34b)
check("bug reproduced: the old read of a list knob does not move when it is turned", before_old == after_old, (before_old, after_old))
check("fixed read follows the list knob: 3 (1/8) -> 6 (1/4D)", (before_new, after_new) == (3, 6), (before_new, after_new))
ok = True
for t in (1, 4, 7, 8, 9, 11, 12):
    new.wr(K + 0x31, bytes([t]))
    for v in (-600, -12, 0, 5, 9, 250, 1000):
        if new.call(s2["plk_knobval"], K, v) != new.call(0x080B0416, K, v):
            ok = False
check("number knobs (Space and JOEBOX's 13): read exactly as before", ok)
check("both reads in the Lock handler go through the fix", new.r32(0x08118ED4) == (s2["plk_knobval"] | 1))

# ---------------------------------------------------------------- 5. PrTime end to end through the stock knob code
# JOEBOX's own registration of Prism Time (literals of the call @0x080f8fe8), the stock bind (0x080b1084) onto the
# Lock Amount knob, the stock turn (0x080b0d54) one detent at a time, the Lock handler's read (plk_knobval), the
# lock (plk_setlock), the voice-start apply (plk_apply) and Prism's Time read (plk_time).
REG = 0x24150000
new.wr(REG, bytes(0x1F4 * 28))
new.w32(0x2401F4FC, REG)
lab_l, names_l, xml_l = (new.r32(a) for a in (0x080F90F8, 0x080F90F0, 0x080F90F4))
lab_l = new.r32(((0x080F8FDA + 4) & ~3) + 0x118)
names_l = new.r32(((0x080F8FE6 + 4) & ~3) + 0x110)
xml_l = new.r32(((0x080F8FD8 + 4) & ~3) + 0x114)
new.call(0x0808C0D8, 0, 0x1A7, lab_l, names_l, stack=(8, xml_l))
check("JOEBOX registers Prism Time as an 8-entry list (type 5)", new.r16(REG + 0x1A7 * 28) == 0x1A7 and new.rd(REG + 0x1A7 * 28 + 2, 1)[0] == 5
      and new.r32(REG + 0x1A7 * 28 + 0xC) == 8, new.cstr(lab_l))
shown = []
new.stubs[0x080C3B98] = lambda: shown.append(new.cstr(new.uc.reg_read(UC_ARM_REG_R1)))
new.stubs[0x080AED14] = lambda: 0                 # the knob's own change message to its view
new.stubs[0x080B0480] = lambda: 0
K = 0x24160000
new.wr(K, bytes(0x400))
new.wr(0x08000200, bytes.fromhex('7047'))           # bx lr: the knob's methods (redraw etc.)
VT = 0x24161000
new.wr(VT, struct.pack('<64I', *([0x08000201] * 64)))
new.w32(K, VT)
store(new, [(0x1A7, 3)])
new.wr(OVR, bytes(20))
new.stubs[0x080FA914] = lambda: P
want = ["1/32", "1/16", "1/8T", "1/8", "1/8D", "1/4", "1/4D", "1/2"]
shown.clear()
import traceback
try:
    new.call(0x080B1084, 0x1A7, 0, K)
except Exception as ex:
    print('crash pc', hex(new.uc.reg_read(UC_ARM_REG_PC)), 'lr', hex(new.uc.reg_read(UC_ARM_REG_LR)), [hex(new.uc.reg_read(r)) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]); raise
# shows PrTime with the knob at 1/32
seen, locked, heard = [shown[-1] if shown else None], [], []
ok_bind = new.rd(K + 0x31, 1)[0] == 5
lid = 0
for step in range(8):
    if step:
        shown.clear()
        new.call(0x080B0D54, K, 400)              # one detent clockwise (400 counts a detent)
        seen.append(shown[-1] if shown else None)
    v = new.call(s2["plk_knobval"], K, new.r32(K + 0x34))
    lid = new.call(s2["plk_setlock"], P, lid, 0x66, 14, stack=(v, 0))
    locked.append(v)
    note(PAD_A, lid)
    heard.append(new.call(s1["plk_time"], SETTINGS, 0x1A7))
check("Lock Amount knob is a list knob when bound to PrTime", ok_bind)
check("knob reads 1/32, 1/16, 1/8T, 1/8, 1/8D, 1/4, 1/4D, 1/2 as it turns", seen == want, seen)
check("every one of the 8 values can be locked (0..7)", locked == list(range(8)), locked)
check("Prism Time plays each locked value", heard == list(range(8)), heard)
new.call(0x080B0D54, K, 400)
check("knob stops at 1/2 (no 9th value)", new.call(s2["plk_knobval"], K, 0) == 7)
for step in range(9):
    new.call(0x080B0D54, K, -400)
check("and turns back down to 1/32", new.call(s2["plk_knobval"], K, 0) == 0)
new.wr(EV, bytes([1]) + bytes(0x1F))
new.call(s2["plk_fmt"], P, lid, TMP)
check('saved as "t:7" and loads back', new.cstr(TMP) == "t:7")

print("FAILS:", fails)
sys.exit(1 if fails else 0)
