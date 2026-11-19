# JOEBOX Prism Lock Targets

A private add-on for **JOEBOX 3 test 3.5.zi**, the unofficial firmware mod for the original 1010music Blackbox. It adds two targets to the sequencer's per-note **Lock** (parameter lock):

| Target    | Locks                 | Amount (bottom-right knob)                               |
|-----------|-----------------------|----------------------------------------------------------|
| `PrSpace` | Prism 1 → Space       | 0.0 % … 100.0 %                                          |
| `PrTime`  | Prism 2 → Time        | 1/32, 1/16, 1/8T, 1/8, 1/8D, 1/4, 1/4D, 1/2              |

## Hardware tested

**Tested on my own Blackbox on 2026-11-19.** Built from JOEBOX 3 test 3.5.zi, installed from the card (BACK + INFO, with BBEXTRA written by JOEBOX's card loader on first boot), and confirmed working:

- `PrSpace` locks Prism 1 Space per note, and unlocked notes go back to the knob.
- `PrTime` Amount knob shows 1/32 … 1/2, and each value locks Prism 2 Time per note.

It has run on that one unit only.

The tested pair's SHA-256:

```
BLACKBOX.bin  9908f1ac443ca2c61405af96491365683bef2302115609e99e1ff4d868cc68b3   (784,608 bytes)
BBEXTRA.BIN   3f2eb70fd439c74757c9c97fe1c85987f4b6e031aa4fc70913af67e12a2c265f   (114,528 bytes)
```

`apply.py` rebuilds exactly this pair from the original JOEBOX 3 test 3.5.zi files.

## How it behaves

- **Per note:** open a sequencer note, press **Lock**, and pick `PrSpace` or `PrTime` under Lock Target. Set the Amount. A note can lock either target, both, or neither. Locked targets show `*` in the list.
- **Reverting:** when the same pad's next note has no Prism lock, Prism goes back to its knob settings. The knobs themselves are never changed.
- **Shared effect:** Prism is one effect for the whole box, so the most recent locked note wins. Another pad's unlocked notes don't cancel it. Loading a project clears any active Prism lock.
- **Master FX:** must be set to **Prism** to hear it.
- **Projects:** locks save with the project as `x:` (Space) and `t:` (Time) in each note's plock text. The original JOEBOX 3 build loads these projects and ignores the two new locks.

## Build the firmware pair

This repo contains no firmware. You need your own copy of **JOEBOX 3 test 3.5.zi** (`BLACKBOX.bin` and `BBEXTRA.BIN`); the script checks their SHA-256 and refuses anything else.

```bash
python3 apply.py /path/to/joebox-3-test-3.5.zi out
```

This writes `out/BLACKBOX.bin` and `out/BBEXTRA.BIN`.

## Install

1. Copy **both** files from `out/` to the root of the microSD card. They are a pair: this `BLACKBOX.bin` only works with this `BBEXTRA.BIN`.
2. Power on while holding **BACK + INFO** to install.
3. On first start, JOEBOX's card loader writes the new `BBEXTRA.BIN` into flash bank 2 and restarts. Leave the power on. Until then Tools shows `!` and Prism is bypassed.

**To go back:** put the original JOEBOX 3 pair on the card and install the same way. Keep stock 3.1.9 too.

**Bootloader:** not touched. `BLACKBOX.bin` stays above `0x08040000` and below the installer's `0x08100000` limit. `BBEXTRA.BIN` goes to bank 2 (it ends at `0x0811BF60`) through JOEBOX's unchanged loader, which never writes bank 1 or the factory calibration sector.

## Repo layout

| Path | What |
|------|------|
| `apply.py` | Patches your JOEBOX 3 pair: 5 calls, ids and checksum in `BLACKBOX.bin`, 15 edits in `BBEXTRA.BIN`, plus the new code appended |
| `src/plk_b2.c`, `src/plk_b2_thunk.S` | Bank 2 code: 15-target lock store / set / save / load, the "unlocked value" lookup, the apply wrapper that sets and clears the Prism override, the list-knob read |
| `src/plk_b1.c` | Bank 1 code: Prism's Space and Time reads return the active lock |
| `src/b1.ld`, `src/b2.ld`, `src/build.sh` | Link addresses and the build (needs an `arm-none-eabi-gcc`; set `CROSS=` to its prefix if it's not on PATH) |
| `prebuilt/` | The compiled code `apply.py` uses, as built from `src/` (rebuilding gives the same bytes) |
| `test/test_plk.py` | 48 emulator checks (Unicorn) |

## Tests

```bash
pip install unicorn capstone
python3 test/test_plk.py out /path/to/joebox-3-test-3.5.zi
```

The checks include:

- 600 random lock edits on JOEBOX's original 13 targets, giving byte-for-byte the same lock memory, ids and save text as JOEBOX's own code.
- Save / load round trips, and damaged text parsing the same way JOEBOX does.
- The Prism override being set, kept and cleared as described above.
- The Lock page list showing all 15 names with `*` marks.
- The `PrTime` knob driven by the firmware's own knob code: it steps through all eight values, each one is locked and played by Prism, and it stops at 1/2.

## How it works (short)

JOEBOX stores each note's locks as a 32-byte record: a mask, then 13 values, with two unused halfwords. `PrSpace` uses the halfword at +30 and `PrTime` the one at +2, so the record size and old projects are unchanged.

The functions that loop over 13 targets (store, set, save, load) are replaced with 15-target versions. The Lock list's count, bounds and name table are extended, and the Amount knob is bound to Prism's own Space and Time settings, so it shows their exact values.

When a voice starts, JOEBOX's apply runs as before, and then the new code sets or clears a Prism override that Prism reads instead of its knobs.

Changing bank 2 also needs a new pairing id and checksum in `BLACKBOX.bin`; `apply.py` writes both.

## Notice

Unofficial; not affiliated with or supported by 1010music or the JOEBOX author. "1010music" and "Blackbox" are trademarks of 1010music LLC. Built on JOEBOX by Justin Joe (MIT-licensed mod code, https://github.com/j3threejay/blackbox-mod). This repo contains no 1010music or JOEBOX firmware. Modified firmware is used at your own risk.
