# Design System: Trade Journal Home / Cockpit Ledger

## 1. Visual Theme & Atmosphere

The homepage should feel like a post-market trading audit desk: quiet, severe, data-rich, and disciplined. It is not a broker landing page and not a social feed. It is a public review board for traders who care about plan quality, execution gaps, emotional state, and repeatable lessons.

Atmosphere scale:

- Density: 8/10, cockpit dense. The page should show useful market and review information immediately.
- Variance: 7/10, asymmetric and editorial, with a strong left narrative and right-side trade tape/chart panel.
- Motion: 5/10, restrained terminal motion. Interactions feel alive but never decorative.

The first viewport must communicate "trading review system" immediately through numbers, instruments, PnL, quality grades, plans, and a chart-like visual. Avoid generic community or SaaS language.

## 2. Color Palette & Roles

- **Terminal Canvas** (#0F1011): Primary page background. Never use pure black.
- **Panel Charcoal** (#141416): Main panel and tape surfaces.
- **Zinc Rail** (#27272A): Borders, dividers, chart grid lines.
- **Soft Ink** (#E4E4E7): Primary text on dark surfaces.
- **Muted Steel** (#A1A1AA): Secondary copy and metadata.
- **Dead Tick** (#71717A): Tertiary labels, inactive navigation, annotations.
- **Audit Green** (#14B8A6): The only accent color. Used for primary active states, profitable values, focus marks, and selected review signals.
- **Risk Red** (#F43F5E): Semantic loss/risk color only. Not a second brand accent.
- **Paper White** (#FAFAFA): Optional light content strip or text surface if a section needs contrast.

Palette rules:

- Maximum one accent: Audit Green.
- No purple, blue neon, outer glows, rainbow gradients, or pure black.
- Use border contrast and spacing before shadows.
- Profits use Audit Green, losses use Risk Red, neutral metadata uses Dead Tick.

## 3. Typography Rules

- **Display:** Satoshi or Geist. Tight tracking, strong weight, controlled scale. Homepage headline uses `clamp(42px, 6vw, 72px)` with line-height around `0.92`.
- **Body:** Satoshi or Geist. Minimum 15px on desktop, 14px on dense metadata. Body copy max width around 56-65 characters.
- **Mono:** JetBrains Mono, SF Mono, Consolas fallback. All numbers, PnL, ticket-like values, dates, quality grades, and account metrics use mono.
- **Chinese text:** Keep hierarchy through weight, spacing, and contrast. Avoid oversized Chinese paragraphs inside compact panels.

Banned:

- Inter as the named premium font.
- Serif fonts in this dashboard context.
- Negative letter spacing on compact metadata. Display text may use tight tracking only where it remains readable.

## 4. Hero Section

The hero is an asymmetric trading command surface:

- Left column: small mono kicker, large headline, short explanatory copy, three metric blocks.
- Right column: chart-like panel plus latest trade tape rows.
- Headline copy: "复盘不是回忆，是交易系统的审计。" This may include an inline market-chip visual between phrases. On mobile the chip must not overlap text.
- Metrics: use real template values from `total_orders`, `total_reviews`, and `total_users`.
- Right chart panel: use CSS grid/chart motif, not stock photos. It should look like an abstract review signal, not a fake live price chart.
- CTA restraint: no more than one primary action if one is used. The existing login/register navigation is enough for unauthenticated users.

The hero must not be centered. It must not include scroll prompts, bouncing arrows, generic marketing claims, or decorative gradient blobs.

## 5. Homepage Content Architecture

After the hero, the homepage keeps the existing data model but changes presentation:

1. **Latest Reviews / Review Tape**
   - Dense table-like rows.
   - Columns: symbol, direction/quality, review lesson excerpt, PnL, username.
   - Use border-bottom dividers instead of floating nested cards.

2. **Public Plans**
   - Compact plan ledger.
   - Show direction, symbol, title, planned date, and risk-relevant values if available.
   - Presentation should feel like planned setups, not blog cards.

3. **Leaderboard**
   - Rank list with mono PnL and trade counts.
   - Use restrained badges for top ranks. No medal-style decorative icons.

4. **Featured Reviews**
   - Elevated only when a high-rating review needs prominence.
   - Use a structured panel or split row, not a generic equal-card feature row.

5. **Market Calendar Links**
   - Keep useful links but style as a utility strip.
   - No promotional copy.

## 6. Component Stylings

Buttons:

- Flat, tactile, no outer glow.
- Active state may translate by `1px`.
- Primary fill uses Audit Green only.
- Minimum touch target: 44px on mobile.

Panels:

- 1px Zinc Rail border.
- Background Panel Charcoal.
- Border radius 8px maximum unless the existing global system requires otherwise.
- Use shadows sparingly; hierarchy should come from layout and dividers.

Rows and Ledgers:

- Dense row height around 44-56px.
- Mono values right aligned.
- Hover changes background subtly using transform/opacity only if animated.

Tags:

- Direction tags: buy/profit lean Audit Green; sell/loss lean Risk Red.
- Quality tags use text and border first, fill only for high-signal states.
- Keep labels short and uppercase for Latin instrument metadata.

Empty states:

- Compact, useful copy that tells the user what data is missing.
- No large illustration-only empty states on the homepage.

## 7. Layout Principles

- Use CSS Grid for hero and content architecture.
- Max-width: 1400px centered for content bands.
- Mobile collapse below 768px into single column.
- No horizontal scroll on mobile.
- No cards inside cards.
- No three equal feature-card row as the primary structure.
- Text and numbers must not overlap or overflow their cells.
- Homepage sections are full-width bands or ledger panels, not nested decorative cards.

Desktop target:

- Hero: two-column asymmetric grid.
- Content: main review ledger plus side utility/plan/leaderboard rail.

Mobile target:

- Hero collapses headline, metrics, chart, tape.
- Metric blocks become stacked or 2-column if space allows.
- Review rows hide lowest-priority fields, but keep symbol, quality/direction, lesson, and PnL when possible.

## 8. Motion & Interaction

- Use CSS transitions only for transform and opacity.
- Hover: subtle `translateY(-1px)` or background shift.
- Active controls: tactile `translateY(1px)`.
- Optional perpetual motion: chart panel may have a very slow opacity pulse on the signal line, but no blinking trading-terminal gimmick.
- No custom cursor.
- No animations on width, height, top, or left.

## 9. Anti-Patterns

Never use:

- Emojis in the homepage UI.
- Inter font.
- Pure black `#000000`.
- Purple, neon blue, or glowing gradients.
- Generic SaaS hero copy such as "Elevate", "Unleash", "Next-Gen", or "Seamless".
- Scroll prompts or bouncing arrows.
- Three equal cards as the main feature row.
- Decorative orbs, bokeh blobs, or unrelated stock imagery.
- Fake perfect metrics like `99.99%`.
- Generic placeholder names such as John Doe or Acme.
- Overlapping absolute-positioned text.

## 10. Implementation Scope

Only redesign the public homepage for this pass:

- `templates/home.html`
- Any homepage-specific CSS either inside the template block or a small homepage section in `static/css/style.css`
- Minimal global CSS token changes only if required for the homepage to render correctly

Do not change:

- Database schema.
- Route behavior.
- Auth flow.
- Trading import logic.
- Other dashboard pages.

## 11. Verification Criteria

The implementation is ready when:

- Homepage renders without template errors.
- Desktop viewport shows the asymmetric Cockpit Ledger hero.
- Mobile viewport has no horizontal overflow.
- Existing dynamic data still renders for latest plans, latest reviews, featured reviews, rankings, and totals.
- No visible garbled Chinese remains on the homepage.
- CSS uses the approved palette and no purple/neon/pure-black values for homepage styling.
- Python template rendering smoke test passes through Flask test client.
