/**
 * Brand raster assets from the committed mark (D-027).
 *
 * public/logo.svg is the source of truth (the SVG itself is produced from
 * the state geometry; see D-027). This script derives every raster asset:
 *   - public/icon-32.png, icon-192.png, icon-512.png (transparent corners)
 *   - public/icon-maskable-512.png (full-bleed peacock, mark in safe zone)
 *   - src/app/opengraph-image.png (mark centred on editorial paper,
 *     alpha-composited — no white box)
 *
 * Run: node scripts/brand-assets.mjs   (sharp comes with Next)
 * favicon.ico is kept as-is; regenerate it from icon-32.png with an ICO
 * encoder if the mark ever changes.
 */
import sharp from "sharp";

const MARK = "public/logo.svg";
const PEACOCK = "#16646e";
const PAPER = "#faf8f3";

async function markPng(size) {
  // density scales the 512px-declared SVG so we never upsample.
  return sharp(MARK, { density: (72 * size) / 512 + 1 })
    .resize(size, size)
    .png()
    .toBuffer();
}

for (const size of [32, 192, 512]) {
  await sharp(await markPng(size)).toFile(`public/icon-${size}.png`);
}

// Maskable: full-bleed background, mark within the ~80% safe zone.
await sharp({
  create: { width: 512, height: 512, channels: 4, background: PEACOCK },
})
  .composite([{ input: await markPng(408), gravity: "centre" }])
  .png()
  .toFile("public/icon-maskable-512.png");

// OG share image: mark only, on paper (D-027) — composite keeps alpha.
await sharp({
  create: { width: 1200, height: 630, channels: 4, background: PAPER },
})
  .composite([{ input: await markPng(420), gravity: "centre" }])
  .flatten({ background: PAPER })
  .png()
  .toFile("src/app/opengraph-image.png");

console.log("brand assets regenerated from", MARK);
