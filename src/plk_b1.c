/*
 * Prism lock targets, bank 1 part: Prism's per-block reads of Space (0x1a3) and Time (0x1a7) see the Lock override
 * (plk_b2.c) while one is active. Bank 1 on purpose: Prism's reader runs before JOEBOX's bank 2 check, so nothing
 * here may call into bank 2 - it only reads the override in RAM.
 */
#include <stdint.h>

#define FN(a) ((a) | 1u)
typedef int (*setting_fn)(const void *store, unsigned param);
typedef float (*pct_fn)(unsigned param);
typedef uint8_t *(*lockpool_fn)(void);
#define fw_setting  ((setting_fn)FN(0x08093e9c))
#define jb_pct      ((pct_fn)FN(0x080f8e04))
#define jb_lockpool ((lockpool_fn)FN(0x080fa914))  /* lock pool, or 0 when bank 2 is not live */

#define OVR_OFF   0x31c0
#define OVR_MAGIC 0x4b4c5250u
struct ovr {
    uint32_t magic;
    int32_t val[2];
    uint32_t own[2];
};

static int over(int k, int *v)
{
    uint8_t *P = jb_lockpool();
    if (!P)
        return 0;
    const volatile struct ovr *o = (const volatile struct ovr *)(P + OVR_OFF);
    if (o->magic != OVR_MAGIC || !o->own[k])
        return 0;
    *v = o->val[k];
    return 1;
}

/* in place of `bl pct` @0x080f97f0 (the four block amounts, ids 0x1a1..0x1a4) */
float plk_pct(unsigned id)
{
    int v;
    if (id == 0x1a3 && over(0, &v))
        return (float)(v < 0 ? 0 : v > 1000 ? 1000 : v) * 0.001f;
    return jb_pct(id);
}

/* in place of `bl fw_setting` @0x080f9826 (Time, 0x1a7) */
int plk_time(const void *store, unsigned id)
{
    int v;
    if (id == 0x1a7 && over(1, &v))
        return v < 0 ? 0 : v > 7 ? 7 : v;
    return fw_setting(store, id);
}
