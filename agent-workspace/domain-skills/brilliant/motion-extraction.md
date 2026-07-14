---
name: brilliant-motion-extraction
description: brilliant.org — welcome/onboarding flow structure, and how to extract their framer-motion animation physics (static DOM inspection fails; you must frame-sample computed styles mid-transition).
---

# Brilliant — onboarding flow + animation extraction

Brilliant's onboarding (`brilliant.org/welcome/?cta_persona=learner`) is a React + Chakra app ("chakra-text", "panda-*" utility classes) animated with framer-motion. The site's signature "high quality" text feel is worth copying, but you cannot read it from the DOM after the fact — this file records both the flow's shape and the sampling technique that works.

## Flow shape

- `/welcome/?cta_persona=learner` opens a multi-screen wizard: Koji intro → motivation question → voice pick ("How do you want me to sound?", Melodic/Deep cards + "Voice off" toggle) → interactive demo lesson on a coordinate grid.
- Screens advance via a single `Continue` button (`button` with exact text "Continue"). Option cards are plain `button`s; selecting does not auto-advance — Continue commits.
- Some screens speak a Koji voice line and auto-advance when it finishes. A sampler you attach to one screen may be gone before you read it back; collect into `window.__x` and read it on a later call.

## The animation pattern (measured Jun 2026)

**Not a typewriter.** Headings are plain blocks (`innerHTML` is text + `<br>` — no per-word/char spans). The entrance is a framer-motion **spring scale pop on the whole block**: scale 0.50 → 0.96 → overshoot peak **1.043** → settle 1.0 over ~600ms. Opacity is already 1 by scale 0.5 (any fade is inside the first ~60ms). Options/content enter ~150–400ms behind the heading.

CSS stand-in that reproduces it (peak matches 1.043 exactly): `animation: pop .55s cubic-bezier(.34,1.56,.64,1) both` with `@keyframes pop{from{opacity:0;transform:scale(.55)}}`.

## How to extract framer-motion physics (generalizes beyond Brilliant)

Static inspection fails: computed `animation` is `none` (framer-motion drives inline styles per frame), and after settle every transform is identity. The bundle is minified React — don't read it. Instead, sample computed styles at rAF resolution, starting the sampler *before* triggering the transition:

```js
window.__trace = []; const t0 = performance.now();
const sample = () => {
  const p = document.querySelector("SELECTOR");      // the element that animates
  if (p) { const cs = getComputedStyle(p);
    window.__trace.push({ t: (performance.now()-t0)|0,
      scale: cs.transform === "none" ? 1 : +cs.transform.slice(7).split(",")[0],
      op: cs.opacity }); }
  if (performance.now() - t0 < 2200) requestAnimationFrame(sample);
};
requestAnimationFrame(sample);
[...document.querySelectorAll("button")].find(b => b.textContent.trim() === "Continue").click();
// read JSON.stringify(window.__trace) in a later call
```

To discover *which* element animates when you don't know the selector, scan everything for non-identity transform / non-1 opacity during the transition and log text snippets.

## Traps

- The OneTrust cookie banner sits in the DOM at `opacity:0` and floods any "find elements with opacity < 1" scan. Exclude `[class*=onetrust],[class*=ot-]` ancestors.
- Rule out per-word stagger by checking the heading's `innerHTML` for spans before assuming one. Brilliant has none; the voice + pop just reads that way.
- Element-level sampling at fixed 60–90ms intervals can entirely miss a fast opacity ramp; use rAF, and treat "opacity already 1 at first sample" as "fade is faster than one frame interval," not "no fade."
