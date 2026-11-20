# Onboarding illustrations

Drop these PNGs in this folder (`miniapp/public/onboarding/`). The app already
points at these exact names, so they appear as soon as the files exist and the
Mini App is rebuilt. A missing file is hidden, so the cards still work without it.

## Format

- PNG with transparency, sRGB.
- Canvas: **535 × 535 px** (the size of the current set), or 1070 × 1070 for @2x.
  Use the same canvas for every image in a set so the cards stay aligned.
  Any consistent size works — the app scales the image to fill the card's
  illustration panel (about **125 × 120 px** on a 350 px card) and anchors it to
  the bottom-right corner, clipped by the card's rounded edge.
- Crop tightly around the subject: head near the top, waist/hips at the bottom
  edge, only a small transparent margin. Large empty margins make the character
  tiny once the image is scaled down.
- Keep the subject centred in the canvas. The app anchors the image itself to the
  right edge, so an off-centre subject would drift into the card border.
- No background, border, text, logo or drop shadow. The card supplies those.
- Match the level-art style (stylized 3D, dark-green shadows, mint/lime rim light).
- Goal, experience and diet cards are cut-out subjects on transparency.
- Equipment cards are full square scenes **with their own background**: the app
  crops them to fill the panel edge-to-edge (`object-fit: cover`), so keep the
  important props away from the outer ~5% of the canvas.

## Goal cards (7)

| File | Shown for | What to draw |
|---|---|---|
| `goal_lose_weight.png` | Female | Woman in athletic wear, hands on hips or one hand at the waist, confident lean silhouette; optional subtle downward-arrow motif behind her. |
| `goal_gain_muscle.png` | Female | Woman flexing one arm or holding a dumbbell at her side; visible toned arms/shoulders. |
| `goal_improve_health.png` | Female | Woman standing relaxed, one hand on the chest or holding an apple, healthy/warm expression; small heart or sparkle accent. |
| `goal_get_in_shape.png` | Female | Woman in a dynamic stretch or light jog, energetic and athletic. |
| `goal_bulk.png` | Male | Muscular man in a power stance, broad silhouette, arms slightly out/flexed. |
| `goal_lean_bulk.png` | Male | Athletic man holding a dumbbell, lean and defined, calm confident pose. |
| `goal_recomp.png` | Male | Balanced athletic build, arms crossed or a circular-arrows accent; confident, not bulky. |

“Prefer not to say” shows all seven goal cards.

## Experience cards (3 male + 3 female)

| File | Shown for | What to draw |
|---|---|---|
| `exp_beginner.png` | Male / unspecified | Man with a light dumbbell or band, simple learning stance; least muscular. |
| `exp_intermediate.png` | Male / unspecified | Man mid-set with dumbbells, confident, visible muscle tone. |
| `exp_advanced.png` | Male / unspecified | Man lifting a heavy barbell or in an intense pose, very muscular; chalk/straps optional. |
| `exp_beginner_female.png` | Female | Woman with a light dumbbell or band, simple learning stance; least muscular. |
| `exp_intermediate_female.png` | Female | Woman mid-set, confident, visible muscle tone. |
| `exp_advanced_female.png` | Female | Woman lifting a heavy weight or in an intense pose, very muscular. |

Order in the app: beginner → intermediate → advanced. The female files currently
reuse the matching female goal illustrations; replace them with dedicated
experience poses when those are drawn.

## Equipment cards (3, shared)

| File | What to draw |
|---|---|
| `eq_full_gym.png` | Compact gym scene: squat rack, barbell and plates, bench, dumbbell rack. |
| `eq_home_dumbbells.png` | Pair of dumbbells on a mat, optionally a small home bench. |
| `eq_bodyweight.png` | Person doing a push-up, pull-up or plank; no equipment. |

## Diet cards (4, shared)

| File | What to draw |
|---|---|
| `diet_none.png` | Balanced plate (grilled protein, rice, vegetables) or fork-and-knife; “no restriction”. |
| `diet_vegetarian.png` | Bowl with eggs, dairy, grains and vegetables; small egg/leaf accent. |
| `diet_vegan.png` | Green bowl with legumes, grains, leafy vegetables and seeds; leaf accent. |
| `diet_pescatarian.png` | Fish fillet with rice and vegetables; small fish accent. |

## Where they are used

`miniapp/src/screens/Onboarding.tsx` maps the answer values to these paths:

```ts
GOAL_ART, EXPERIENCE_ART, EQUIPMENT_ART, DIET_ART
```

After adding files, run `npm run build` in `miniapp/` (the API serves the built
app), or just keep the Vite dev server running.

## Not part of this folder

- **Level characters:** already present in `assets/levels/male_1_rookie.png` …
  `male_5_pro.png`. The app currently always uses the male set; female level art
  is not wired yet.
- **Muscle anatomy cards:** see `public/muscles/README.md` (10 square PNGs:
  chest, back, shoulders, biceps, triceps, core, quads, hamstrings, glutes, calves).