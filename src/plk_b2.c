/*
 * Prism lock targets for JOEBOX 3 test 3.5.zi's sequencer Lock (bank 2 part).
 *
 * Adds two Lock targets to the 13 JOEBOX has: 13 = "PrSpace" (Prism 1 Space, 0.0 .. 100.0 %, the global setting
 * 0x1a3) and 14 = "PrTime" (Prism 2 Time, 1/32 .. 1/2, the global list 0x1a7). The Amount knob is bound to those
 * settings, so it shows and steps exactly like the Prism knobs.
 *
 * Lock record (JOEBOX, 32 bytes, unchanged size): u16 mask, i16 at +2 (was always 0), i16 value[13] at +4, i16 at +30
 * (was unused). Target 13's value lives at +30, target 14's at +2. Records made by the stock JOEBOX code have
 * both at 0 and bits 13/14 clear, so old projects load as before.
 *
 * Replaced here (callers repointed): the record store (intern), set-one-target (setlock), save (fmt) and load
 * (parse) - each now knows 15 targets - and the "unlocked value" lookup (base) for the two new targets.
 * apply runs JOEBOX's own apply, then sets / clears a Prism override: a locked note on a pad sets it (owner =
 * that pad), the owner pad's next note without that lock clears it. Prism (bank 1) reads the override in place of
 * the knob, so the knob's own value is never written.
 */
#include <stdint.h>

#define FN(a) ((a) | 1u)

/* JOEBOX bank 2 */
typedef uint8_t *(*pool_fn)(void *owner);
typedef uint8_t *(*lookup_fn)(void *owner, uint32_t id);
typedef int (*base_fn)(void *owner, void *event, int idx);
typedef void (*apply_fn)(void *owner, void *voice, void *pad, int cls);
typedef void (*reset_fn)(void *owner);
#define jb_pool   ((pool_fn)FN(0x0811825c))
#define jb_lookup ((lookup_fn)FN(0x081182ee))
#define jb_base   ((base_fn)FN(0x08118c00))
#define jb_apply  ((apply_fn)FN(0x08118634))
#define jb_reset  ((reset_fn)FN(0x081182d4))
/* stock */
typedef int (*setting_fn)(const void *store, unsigned param);
typedef const char *(*xml_attr_fn)(void *elem, const char *name, const char *dflt);
#define fw_setting  ((setting_fn)FN(0x08093e9c))
#define fw_xml_attr ((xml_attr_fn)FN(0x0804a66d))
#define SETTINGS    ((const void *)0x24028d18u)

#define NT        15
#define P_SPACE   0x1a3
#define P_TIME    0x1a7
#define REC_MAX   0x100
#define LOCK_TAG  0xb7000000u

/* the Prism override, in the lock pool's unused tail (pool + 0x31c0 .. 0x31d4; the pool may use up to 0x3200) */
#define OVR_OFF   0x31c0
#define OVR_MAGIC 0x4b4c5250u            /* "PRLK" */
struct ovr {
    uint32_t magic;
    int32_t val[2];                      /* [0] Space 0..1000, [1] Time 0..7 */
    uint32_t own[2];                     /* the pad object that set it; 0 = not active */
};
_Static_assert(OVR_OFF + sizeof(struct ovr) <= 0x3200, "override must stay inside the pool");

/* names, 7 characters at most: the list draws '*' + name in 9-byte cells */
static const char n13[] = "PrSpace", n14[] = "PrTime";
__attribute__((used)) const char *const plk_names[NT] = {
    (const char *)0x081194a9, (const char *)0x081194af, (const char *)0x081194b6, (const char *)0x081194ba,
    (const char *)0x081194c1, (const char *)0x081194c7, (const char *)0x081194cf, (const char *)0x081194d7,
    (const char *)0x081194db, (const char *)0x081194df, (const char *)0x081194e5, (const char *)0x081194e9,
    (const char *)0x081194ef, n13, n14,
};
/* parameter the Amount knob is bound to, per target (JOEBOX's 13, then the two Prism settings) */
__attribute__((used)) const int16_t plk_pids[NT + 1] = {
    0x5c, 0xc8, 0x11, 0x3c, 0x3e, 0x3f, 0x40, 0xd9, 0xda, 0x02, 0x62, 0x02, 0x02, P_SPACE, P_TIME, 0,
};
static const char codes[NT] = {'0', '1', '2', '3', '4', '5', '6', 'f', 'g', 'l', 'p', 's', 'n', 'x', 't'};

static inline int16_t *slot(void *rec, int i)
{
    uint8_t *r = (uint8_t *)rec;
    return (int16_t *)(i < 13 ? r + 4 + 2 * i : i == 13 ? r + 30 : r + 2);
}

static inline uint16_t *mask_of(void *rec) { return (uint16_t *)rec; }

static void zero16(uint16_t *t)
{
    volatile uint16_t *v = t;
    for (int i = 0; i < 16; i++)
        v[i] = 0;
}

/* JOEBOX 0x08118322, 15 targets */
uint32_t plk_intern(void *owner, void *tmp)
{
    uint8_t *P = jb_pool(owner);
    unsigned m = *mask_of(tmp);
    if (!m)
        return 0;
    unsigned n = *(uint16_t *)(P + 6);
    for (unsigned k = 0; k < n; k++) {
        uint8_t *rec = P + 0x20 + 32 * k;
        if (*mask_of(rec) != m)
            continue;
        int same = 1;
        for (int i = 0; i < NT; i++)
            if (((m >> i) & 1) && *slot(rec, i) != *slot(tmp, i)) {
                same = 0;
                break;
            }
        if (same)
            return LOCK_TAG | (uint32_t)P[4] << 16 | k;
    }
    if (n >= REC_MAX)
        return 0;
    uint8_t *rec = P + 0x20 + 32 * n;
    *mask_of(rec) = (uint16_t)m;
    for (int i = 0; i < NT; i++)
        *slot(rec, i) = ((m >> i) & 1) ? *slot(tmp, i) : 0;
    *(uint16_t *)(P + 6) = (uint16_t)(n + 1);
    return LOCK_TAG | (uint32_t)P[4] << 16 | n;
}

/* JOEBOX 0x081183ba, 15 targets */
uint32_t plk_setlock(void *owner, uint32_t id, uint32_t who, unsigned bit, int value, int clear)
{
    uint8_t *P = jb_pool(owner);
    uint8_t *rec = jb_lookup(owner, id);
    uint16_t tmp[16];
    zero16(tmp);
    unsigned m0 = 0;
    if (rec) {
        for (int i = 0; i < NT; i++)
            *slot(tmp, i) = *slot(rec, i);
        m0 = *mask_of(rec);
    }
    unsigned b = (1u << bit) & 0xffffu, m;
    if (clear) {
        m = m0 & ~b;
    } else {
        m = m0 | b;
        *slot(tmp, (int)bit) = (int16_t)value;
    }
    tmp[0] = (uint16_t)m;
    if (!m) {
        *(uint32_t *)(P + 0x14) = 0;
        return 0;
    }
    if (rec && *(uint32_t *)(P + 0x14) == id && *(uint32_t *)(P + 0x18) == who) {
        *mask_of(rec) = (uint16_t)m;
        for (int i = 0; i < NT; i++)
            *slot(rec, i) = *slot(tmp, i);
        return id;
    }
    unsigned n0 = *(uint16_t *)(P + 6);
    uint32_t nid = plk_intern(owner, tmp);
    if (!nid)
        return id;
    *(uint32_t *)(P + 0x14) = *(uint16_t *)(P + 6) > n0 ? nid : 0;
    *(uint32_t *)(P + 0x18) = who;
    return nid;
}

/* JOEBOX 0x08118496: "c:v,c:v" into the save buffer (120 bytes at the one caller: kept under that) */
#define FMT_CAP 118
int plk_fmt(void *owner, uint32_t id, char *out)
{
    uint8_t *rec = jb_lookup(owner, id);
    if (!rec)
        return 0;
    char *p = out;
    for (int i = 0; i < NT; i++) {
        if (!((*mask_of(rec) >> i) & 1))
            continue;
        char t[12];
        int n = 0;
        if (p != out)
            t[n++] = ',';
        t[n++] = codes[i];
        t[n++] = ':';
        int v = *slot(rec, i);
        if (v < 0) {
            t[n++] = '-';
            v = -v;
        }
        char d[5];
        int nd = 0;
        do {
            d[nd++] = (char)('0' + v % 10);
            v /= 10;
        } while (v && nd < 5);
        while (nd)
            t[n++] = d[--nd];
        if ((p - out) + n > FMT_CAP)
            break;
        for (int k = 0; k < n; k++)
            *p++ = t[k];
    }
    *p = 0;
    return 1;
}

/* JOEBOX 0x08118530: an event's "plock" attribute back into a record */
void plk_parse(void *owner, void *elem, uint8_t *ev)
{
    if (ev[0] != 1 || !elem)
        return;
    *(uint32_t *)(ev + 0x14) = 0;
    const char *s = fw_xml_attr(elem, "plock", 0);
    if (!s)
        return;
    uint16_t tmp[16];
    zero16(tmp);
    unsigned m = 0;
    int any = 0;
    for (;;) {
        char c = *s;
        if (!c)
            break;
        int k = 0;
        while (k < NT && codes[k] != c)
            k++;
        if (c == ',' || c == ':' || s[1] != ':')
            return;
        const char *q = s + 2;
        int neg = *q == '-';
        q += neg;
        int v = 0, nd = 0;
        while (nd < 5 && *q >= '0' && *q <= '9') {
            v = v * 10 + (*q - '0');
            q++;
            nd++;
        }
        if (!nd)
            return;
        if (k < NT) {
            m |= 1u << k;
            *slot(tmp, k) = (int16_t)(neg ? -v : v);
            any = 1;
        }
        if (*q == ',')
            s = q + 1;
        else if (*q == 0)
            s = q;
        else
            return;
    }
    if (any)
        tmp[0] = (uint16_t)m;
    *(uint32_t *)(ev + 0x14) = plk_intern(owner, tmp);
}

/* JOEBOX 0x08118c00 with the two Prism targets: their unlocked value is the Prism knob */
int plk_base(void *owner, void *event, int idx)
{
    if (idx == 13)
        return fw_setting(SETTINGS, P_SPACE);
    if (idx == 14)
        return fw_setting(SETTINGS, P_TIME);
    return jb_base(owner, event, idx);
}

/* JOEBOX 0x08118634 + the Prism override. Runs at every voice start (audio task), as JOEBOX's apply does. */
void plk_apply(void *owner, void *voice, void *pad, int cls)
{
    jb_apply(owner, voice, pad, cls);
    uint8_t *P = jb_pool(owner);
    struct ovr *o = (struct ovr *)(P + OVR_OFF);
    if (o->magic != OVR_MAGIC) {
        o->own[0] = o->own[1] = 0;
        o->magic = OVR_MAGIC;
    }
    uint32_t id = *(uint32_t *)(P + 8);
    uint8_t *rec = id && *(void **)(P + 0xc) == pad ? jb_lookup(owner, id) : 0;
    unsigned m = rec ? *mask_of(rec) : 0;
    for (int k = 0; k < 2; k++) {
        if ((m >> (13 + k)) & 1) {
            int v = *slot(rec, 13 + k);
            int hi = k ? 7 : 1000;
            o->val[k] = v < 0 ? 0 : v > hi ? hi : v;
            o->own[k] = (uint32_t)pad;
        } else if (o->own[k] == (uint32_t)pad) {
            o->own[k] = 0;
        }
    }
}

/* JOEBOX 0x081182d4 (sequences cleared / loaded): no override survives it */
void plk_reset(void *owner)
{
    uint8_t *P = jb_pool(owner);
    struct ovr *o = (struct ovr *)(P + OVR_OFF);
    o->own[0] = o->own[1] = 0;
    o->magic = OVR_MAGIC;
    jb_reset(owner);
}

/*
 * The Lock page's Amount knob, read before and after a turn (JOEBOX's handler @0x08118df8, through the literal
 * @0x08118ed4, which held the stock 0x080b0416). That stock read takes the knob's +0x34, which a NUMBER knob
 * updates as it turns; a LIST knob (types 5 / 6: PrTime, bound to Prism Time) steps its index at +0x38 and leaves
 * +0x34 alone, so the handler never saw a change and no PrTime lock was ever made. List knobs: the index.
 */
typedef int (*knobconv_fn)(void *knob, int v);
#define fw_knobconv ((knobconv_fn)FN(0x080b0416))
int plk_knobval(uint8_t *knob, int v)
{
    uint8_t type = knob[0x31];
    if (type == 5 || type == 6)
        return *(volatile int32_t *)(knob + 0x38);
    return fw_knobconv(knob, v);
}
