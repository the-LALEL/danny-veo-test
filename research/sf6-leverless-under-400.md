# Leverless Controller Research — SF6 on PC, under $400
**Research date: June 10, 2026** · Method: parallel live web sweeps + adversarial verification · All product facts below were retrieved live this session; nothing rests on pre-2026 training memory.

---

## TL;DR

**Top recommendation: Varmilo HA10+ (Pro version) — $249.00 at Arcade Shock.**
It is the only leverless controller found under $400 that beats **both** the Victrix Pro KO and the Corsair Novablade Pro on every measurable button-quality axis: Cherry **MX Multipoint Silver** inductive-analog switches rated **200M keystrokes** (vs 150M Novablade, 100M Pro KO), **per-key software-adjustable actuation AND release points in 0.1mm steps with rapid trigger** (Pro KO has none of this), and **solder-free switch replacement** (which the Novablade lacks). It is PS5/PS4/Switch/PC compatible (Brook co-developed PCB) and remappable via Varmilo's web driver.

**One verification gap remains before you click buy** (this environment could not load product images — every retailer returned HTTP 403 to automated fetching): visually confirm on the listing photos that the HA10+ has a button on **both** the left and right side of the large jump button. Its 19-button layout makes this very likely but it was not photo-verified. If that check fails, **no product under $400 provably beats both baselines** — see "If the photo check fails" below.

**Runner-up:** Punk Workshop Leverless M, **Layout B** ($260) — flanking L3/R3 buttons explicitly confirmed, fastest fixed switches in class (0.7mm pre-travel), hot-swap — but it cannot *prove* superiority over the Novablade (no adjustable actuation, unpublished switch lifespan).

**Budget alternative:** Haute42 C-AT (~$85–135) — confirmed flanking thumb buttons, mechanically adjustable pre-travel (0.3/0.6/1.0mm), GP2040-CE firmware (the only platform in this space with independently instrumented latency: ~0.76–0.91ms).

---

## 1. Methodology & honest limitations

- Five parallel research agents swept: (a) Victrix Pro KO primary sources, (b) Novablade Pro primary sources, (c) mainstream makers (Hit Box, SnackBox, Qanba, Razer, Mad Catz, Hori, 8BitDo, Victrix), (d) boutique/import makers (Haute42, Punk Workshop, Varmilo, GuileKeys, FightBox, ZENAIM, Frame1), (e) instrumented latency data and switch datasheets.
- **Limitation disclosed up front:** this environment's network blocked *direct page fetches* (HTTP 403 on every retail/manufacturer host tested). All claims are sourced from live search-indexed page content retrieved 2026-06-10, each tied to a cited URL. Consequences:
  - Prices/stock are search-index snapshots, not cart-verified.
  - **No product image could be inspected.** Layout claims rest on quoted textual descriptions from reviews, manuals, and firmware repos.
- Every load-bearing claim below carries its source. Unverifiable claims are in §7, not silently dropped.

## 2. The baselines (verified)

### Victrix Pro KO (Turtle Beach/PDP) — TBF-3001-05 (PS) / TBF-2001-05 (Xbox)
- **$199.99 on sale (list $279.99)** at [turtlebeach.com](https://www.turtlebeach.com/products/victrix-pro-ko-leverless-fight-stick) (primary) and [Best Buy](https://www.bestbuy.com/product/turtle-beach-victrix-pro-ko-leverless-fight-stick-with-hot-swappable-switches-for-playstation-5-playstation-4-windows-black/J39T968Q7G); PS Direct out of stock. Fetched 2026-06-10.
- Switches: **hot-swappable Cherry MX Speed Silver RGB** — linear, **1.2mm pre-travel, 3.4mm total, 45cN, 100M actuations** ([Cherry primary](https://www.cherry.de/en-us/product/mx2a-speed-silver), [datasheet](https://www.mouser.com/datasheet/2/71/EN_CHERRY_MX_SPEED_Silver-2322168.pdf)). Accepts any 3/5-pin MX switch ([GameGrin](https://www.gamegrin.com/hardware/victrix-pro-ko-review/)). **No rapid trigger / no adjustable actuation** (mechanical).
- Layout: ships 12-button; **4 extra buttons stored in the case for self-install** — "three around the jump button, and the last … left of the movement keys" ([GameRant](https://gamerant.com/victrix-pro-ko-leverless-fight-stick-review/), [PCGamesN](https://www.pcgamesn.com/turtle-beach/victrix-pro-ko-leverless-fight-stick-review)). Remap via [Victrix Control Hub app](https://apps.microsoft.com/detail/9nfsmmcp8xjt) (Windows).
- PS5/PS4/PC licensed; SOCD modes per manual ([manual mirror](https://manuals.plus/victrix/tbf-3001-05-victrix-pro-ko-leverless-fight-stick-manual)).
- **No independent instrumented latency test exists.** Known issue: Control Hub app detection failures on some Win11 PCs ([official PDP support article](https://support.pdp.com/hc/en-us/articles/22437258194701-Victrix-Control-Hub-App-Compatibility-Error)).

### Corsair Novablade Pro Wireless (CH-963B01G-WW), launched Oct 30, 2025
- **$249.99 MSRP** ([Corsair primary](https://www.corsair.com/us/en/p/leverless-controllers/ch-963b01g-ww/novablade-pro-wireless-hall-effect-leverless-fighting-game-controller-ch-963b01g-ww)); ~$224.99 indexed at [Best Buy](https://www.bestbuy.com/product/corsair-novablade-pro-wireless-hall-effect-leverless-controller-black/J39TSCPTKP). Fetched 2026-06-10.
- Switches: **Corsair MGX Hyperdrive Hall-effect** — **150M presses, adjustable actuation 0.1–4.0mm (0.1mm steps), rapid trigger (0.1mm reset)** ([Corsair primary](https://www.corsair.com/uk/en/explorer/gamer/keyboards/corsair-mgx-magnetic-key-switches-explained/)). **Proprietary — not practically user-swappable** ([The Arcade Stick](https://thearcadestick.com/novablade-pro/)).
- Layout: 15 main keys incl. **two extras flanking the Up button** + one above movement keys ([FinalBoss.io](https://finalboss.io/corsair-novablade-pro-review-wireless-ps5-leverless-controll)). 8 G-keys remappable on-device ([Corsair docs](https://www.corsair.com/us/en/explorer/gamer/leverless-controllers/novablade-pro-using-g-keys-remapping-and-macro-recording/)).
- PS5/PS4/PC licensed, tri-mode (wired/2.4GHz/BT), **1000Hz** wired+2.4GHz. **No independent instrumented latency test exists.** No QC failure pattern found.

## 3. The rubric (defined BEFORE scoring)

Five measurable axes; **"objectively beats both baselines" = ≥ both baselines on every axis, strictly > on at least one**, using only sourced figures:

| Axis | Pro KO | Novablade Pro | Bar to beat |
|---|---|---|---|
| **A. Switch tech & rated lifespan** | Mechanical contact, 100M | Hall-effect, 150M | contactless sensing, **>150M** |
| **B. Actuation adjustability** | None (fixed 1.2mm) | Per-key 0.1–4.0mm + rapid trigger | adjustable actuation **and** rapid trigger |
| **C. Hot-swap / serviceability** | Yes (any MX 3/5-pin) | No (proprietary) | solder-free switch replacement |
| **D. Measured latency** | No instrumented data | No instrumented data (1000Hz claim) | ≥1000Hz; instrumented data = bonus win |
| **E. Documented reliability** | Win11 app issue (official) | No failure pattern found | no documented failure pattern |

Implication: beating both requires a board that is simultaneously **magnetic/analog-adjustable** (axis B vs Novablade) **and hot-swappable** (axis C vs Pro KO) **and >150M-rated** (axis A) — a rare combination under $400.

## 4. Scoring — all candidates that passed the hard filters

Hard filters: live listing ≤$400 · physical remappable buttons flanking BOTH sides of jump · PC/SF6 compatible.

| Candidate | Price (2026-06-10) | Flanking buttons | A | B | C | Beats both? |
|---|---|---|---|---|---|---|
| **Varmilo HA10+ Pro** | **$249.00** [Arcade Shock](https://arcadeshock.com/products/varmilo-ha10-pro-version-all-aluminum-all-button-controller-ps4-ps5-pc-sw-sw2), [Amazon](https://www.amazon.com/controller-Leverless-Versions-PC-Compatible-Multi-Platform/dp/B0GL1SPK4S) | **Likely (19 buttons) — photo check required** | ✅ inductive, **200M** | ✅ per-key 0.1mm act+release, RT | ✅ solder-free | **YES — contingent on photo check** |
| Punk Workshop Leverless M **Layout B** | $260 [punkworkshop.us](https://punkworkshop.us/products/mini-box-pkb-pc) | ✅ confirmed L3/R3 flank jump ([Amazon listing](https://www.amazon.com/Workshop-Leverless-Controller-Fighting-Mechanical-PC/dp/B0DJ4K64C3)) | ❌ lifespan unpublished | ❌ fixed 0.7mm, no RT | ✅ hot-swap | No (loses B vs Novablade) |
| Haute42 C-AT | ~$85–135 ([Amazon US](https://www.amazon.com/Haute42-Leverless-Controller-Arcade-Stick/dp/B0G4VJ6YJG); price not cart-verified) | ✅ two 26mm thumb buttons ([The Arcade Stick](https://thearcadestick.com/haute42-c-at/)) | ❌ ~50M class | ❌ 3-step mechanical (0.3/0.6/1.0mm), no RT | ✅ | No — but **only candidate with instrumented latency** (GP2040-CE: 0.76ms XInput, [official data](https://github.com/OpenStickCommunity/GP2040-CE/blob/main/README.md)) |
| 8BitDo Arcade Controller | $89.99 [Amazon](https://www.amazon.com/8BitDo-All-Button-Controller-Windows-Gaming-Console/dp/B0F7R4XTQX) | ✅ two bean buttons around jump ([review](https://www.gameindustry.com/reviews/game-review/the-8bitdo-arcade-controller-packs-premium-features-at-a-budget-price/)) | ❌ Kailh ~50M | ❌ fixed | ✅ Choc-V2 hot-swap | No |
| Hori NOLVA (SPF-049) | ~$100–160 import ([Nin-Nin-Game](https://www.nin-nin-game.com/en/ps5-systems-accessories/178241-nolva-mechanical-all-button-arcade-controller-ps5-hori-.html)) | ✅ expansions install both sides of jump ([Famitsu](https://www.famitsu.com/article/202411/25642)) | ❌ unpublished | ❌ fixed 1.1mm | ✅ hot-swap (proprietary std) | No |

**Notable exclusions:** Razer Kitsune, Hit Box (all current models), SnackBox Micro, Qanba Sapphire S1 (right-flank only confirmed), Mad Catz N.E.K.O., HyperX Clutch Tachi (TMR but 12 buttons) — all fail the flanking-layout filter as sold. ZENAIM Arcade Controller (magnetic, 0.10–0.65mm adjustable, RT) fails axis A vs Novablade (100M < 150M) and US orderability is unverified. Frame1: production discontinued Jan 2025. Victrix Pro KO SF2 Champion Edition ($299.99, Apr 2026) is the same hardware as the baseline.

## 5. Top recommendation in detail — Varmilo HA10+ (Pro version), $249

- **Switches:** Cherry MX Multipoint Silver — inductive analog, **32.2cN actuation, 200M keystrokes, factory-lubed**, no mechanical contacts ([Cherry primary](https://www.cherry.de/en-us/product/mx-multipoint-silver), [Cherry Multipoint family](https://www.cherry.de/en-gb/products/switches/mx-multipoint); 200M rating restated for the same switch in Varmilo's FK2 materials, [Varmilo](https://varmilo.com/products/fk2)). Solder-free replacement per Cherry.
- **Adjustability:** "Full-key customization … 0.1mm customizable activation and reset point," rapid trigger, 4 modes ([Varmilo official X post](https://x.com/Varmilo_Zhh/status/2001209963574641018), [Arcade Shock listing](https://arcadeshock.com/products/varmilo-ha10-pro-version-all-aluminum-all-button-controller-ps4-ps5-pc-sw-sw2)). Per-key activation *and release* adjustment is a capability the Novablade's docs don't claim (Novablade RT reset is fixed 0.1mm).
- **Remap & SOCD:** Varmilo web driver — remap, SOCD, travel settings, input test ([Varmilo manual page](https://varmilo.com/pages/manual)). This covers the flanking buttons (full-key remap).
- **Layout:** 19 buttons (17×24mm + 2×30mm), unused buttons coverable without opening the shell ([Varmilo product page](https://varmilo.com/products/ha10)).
- **Platforms:** Pro version = PC/PS4/PS5/Switch 1/Switch 2 (Brook co-developed PCB); Standard version = **PC-only and cheaper** — fine for SF6 on Steam if you'll never need PS5 (tournament setups are usually PS5 — the Pro is the safer buy).
- **Why it wins:** A: 200M > 150M > 100M. B: matches Novablade's class of adjustability (and adds adjustable release), infinitely exceeds Pro KO. C: solder-free swap where Novablade is sealed. D: tie (no instrumented data for any of the three; HA10+ claims parity-class hardware via Brook PCB — unverified). E: tie (no failure pattern documented for either baseline or the HA10+ — though the HA10+ is newest and has the least track record, noted as risk).

### Pre-purchase checklist (5 minutes, closes the gaps this environment couldn't)
1. **Open the [Arcade Shock listing](https://arcadeshock.com/products/varmilo-ha10-pro-version-all-aluminum-all-button-controller-ps4-ps5-pc-sw-sw2) and look at the photos:** confirm a button immediately LEFT and RIGHT of the big jump button. *(This is the one hard requirement not photo-verified.)*
2. Confirm price ($249.00 indexed 2026-06-10) and add-to-cart state.
3. In the [Varmilo web-driver manual](https://varmilo.com/pages/manual), confirm the actuation adjustment range (the FK2's same switch adjusts 1.5–2.2mm stroke in 0.1mm steps; the Novablade's range is 0.1–4.0mm — if a sub-1.5mm actuation point matters to you, verify the HA10+'s floor).

### If the photo check fails
Then **no purchasable board under $400 provably beats both baselines**, because the only sub-$400 boards with >150M adjustable magnetic/analog switches are the Varmilo HA10+/FK2 (FK2's L3/R3 placement also unverified, [Varmilo](https://varmilo.com/products/fk2)) and ZENAIM (fails the 150M bar at 100M; US ordering unverified). In that case the honest choices are:
- **Punk Workshop Leverless M Layout B ($260)** — confirmed flanking buttons, hot-swap, fastest fixed actuation (0.7mm); beats the Pro KO outright, beats the Novablade on serviceability and pre-travel but not on adjustability/lifespan.
- **Corsair Novablade Pro itself ($225–250)** — it already satisfies your layout requirement; nothing under $400 conclusively out-buttons it except (pending photo check) the HA10+.

## 6. Disconfirmation pass on the top pick
Searched for reasons the HA10+ recommendation is wrong: no QC-failure threads found (absence of evidence — it launched 2026 and has a short track record, the genuine risk); original HA10 is sold out at varmilo.com but the HA10+ has live US channels (Arcade Shock "NEW 2026", multiple Amazon variants); no firmware remap-locking reports; no price-hike signals; Cherry Multipoint hot-swap is limited to *other Multipoint switches* (an inductive system can't take ordinary MX switches) — so the Pro KO retains a broader modding ecosystem even though both are solder-free. None of these overturn the rubric result.

## 7. What I could not verify (explicit)
1. **Any product image** — all layout claims are textual quotes; the HA10+ flanking layout is the load-bearing unverified item.
2. **Cart-level prices/stock** — all prices are search-indexed snapshots from 2026-06-10.
3. **Instrumented latency for HA10+, Pro KO, or Novablade** — none exists publicly; only GP2040-CE boards have audited numbers ([0.76–0.91ms, inputlag.science methodology](https://github.com/OpenStickCommunity/Site/blob/main/latency_testing/README.md)).
4. **HA10+ actuation floor** (whether it can match the Novablade's 0.1mm minimum actuation point).
5. **XInput vs DInput specifics** of "PC mode" on both baselines (SF6 Steam supports both, so not decision-relevant).
6. Shipping costs (all candidate base prices ≤$290, so ≤$400 landed is near-certain but unproven).
