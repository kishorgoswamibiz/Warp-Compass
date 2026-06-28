/**
 * Zero-dependency PWA icon generator (Phase 6). Emits a branded compass mark — green full-bleed
 * background (maskable-safe) with a white ring + N/S needle — as icon-192.png and icon-512.png,
 * plus a matching favicon.svg, into pwa/public/. Uses only node:zlib (manual PNG encoder), so it
 * needs no image libraries. Re-run with `node scripts/gen-icons.mjs` if the brand mark changes.
 */
import { deflateSync } from "node:zlib";
import { writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const PUBLIC = resolve(HERE, "..", "public");
mkdirSync(PUBLIC, { recursive: true });

// Brand palette (theme.css).
const GREEN = [0x15, 0xc9, 0x5b];
const GREEN_LT = [0xbf, 0xf0, 0xd2];
const WHITE = [0xff, 0xff, 0xff];

const crcTable = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = crcTable[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const typeBuf = Buffer.from(type, "ascii");
  const body = Buffer.concat([typeBuf, data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body), 0);
  return Buffer.concat([len, body, crc]);
}

function renderRGBA(size) {
  const buf = Buffer.alloc(size * size * 4);
  const c = (size - 1) / 2;
  const rOuter = size * 0.4;
  const rInner = size * 0.355;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = x - c;
      const dy = y - c;
      const dist = Math.hypot(dx, dy);
      let rgb = GREEN;
      // ring
      if (dist <= rOuter && dist >= rInner) rgb = WHITE;
      // N-S needle (tall thin diamond) — white
      const ns = Math.abs(dx) / (size * 0.07) + Math.abs(dy) / (size * 0.3);
      if (ns <= 1) rgb = WHITE;
      // E-W needle (wide diamond) — light green so the two halves read distinctly
      const ew = Math.abs(dx) / (size * 0.3) + Math.abs(dy) / (size * 0.07);
      if (ew <= 1 && ns > 1) rgb = GREEN_LT;
      // center hub
      if (dist <= size * 0.05) rgb = WHITE;
      const i = (y * size + x) * 4;
      buf[i] = rgb[0];
      buf[i + 1] = rgb[1];
      buf[i + 2] = rgb[2];
      buf[i + 3] = 0xff;
    }
  }
  return buf;
}

function encodePNG(size) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // color type RGBA
  // 10,11,12 = compression/filter/interlace = 0
  const rgba = renderRGBA(size);
  // add filter byte (0) per scanline
  const stride = size * 4;
  const raw = Buffer.alloc((stride + 1) * size);
  for (let y = 0; y < size; y++) {
    raw[y * (stride + 1)] = 0;
    rgba.copy(raw, y * (stride + 1) + 1, y * stride, y * stride + stride);
  }
  const idat = deflateSync(raw, { level: 9 });
  return Buffer.concat([
    sig,
    chunk("IHDR", ihdr),
    chunk("IDAT", idat),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

for (const size of [192, 512]) {
  const out = resolve(PUBLIC, `icon-${size}.png`);
  writeFileSync(out, encodePNG(size));
  console.log(`wrote ${out}`);
}

const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" rx="22" fill="#15c95b"/>
  <circle cx="50" cy="50" r="40" fill="none" stroke="#fff" stroke-width="4.5"/>
  <polygon points="50,18 57,50 50,82 43,50" fill="#fff"/>
  <polygon points="18,50 50,43 82,50 50,57" fill="#bff0d2"/>
  <circle cx="50" cy="50" r="5" fill="#fff"/>
</svg>
`;
const favPath = resolve(PUBLIC, "favicon.svg");
writeFileSync(favPath, svg);
console.log(`wrote ${favPath}`);
