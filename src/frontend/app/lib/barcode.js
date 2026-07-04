// Dependency-free Code 128 (subset B) SVG barcode generator, used for the
// internal-coding labels and the receipt footer. Encodes any ASCII 32–126
// string; returns an SVG string sized for a thermal/label printer.

// Code 128 bar patterns (each digit = module width, alternating bar/space).
const PATTERNS = [
  "212222","222122","222221","121223","121322","131222","122213","122312","132212","221213",
  "221312","231212","112232","122132","122231","113222","123122","123221","223211","221132",
  "221231","213212","223112","312131","311222","321122","321221","312212","322112","322211",
  "212123","212321","232121","111323","131123","131321","112313","132113","132311","211313",
  "231113","231311","112133","112331","132131","113123","113321","133121","313121","211331",
  "231131","213113","213311","213131","311123","311321","331121","312113","312311","332111",
  "314111","221411","431111","111224","111422","121124","121421","141122","141221","112214",
  "112412","122114","122411","142112","142211","241211","221114","413111","241112","134111",
  "111242","121142","121241","114212","124112","124211","411212","421112","421211","212141",
  "214121","412121","111143","111341","131141","114113","114311","411113","411311","113141",
  "114131","311141","411131","211412","211214","211232","2331112",
];
const START_B = 104;
const STOP = 106;

export function code128Svg(text, { height = 44, moduleWidth = 2, showText = true } = {}) {
  const chars = String(text || "").split("");
  if (chars.length === 0) return "";
  const codes = [START_B];
  for (const ch of chars) {
    const v = ch.charCodeAt(0) - 32;
    if (v < 0 || v > 94) continue; // skip non-encodable chars
    codes.push(v);
  }
  let checksum = codes[0];
  for (let i = 1; i < codes.length; i++) checksum += codes[i] * i;
  codes.push(checksum % 103, STOP);

  let x = 10; // quiet zone
  let bars = "";
  for (const code of codes) {
    const pat = PATTERNS[code];
    for (let i = 0; i < pat.length; i++) {
      const w = Number(pat[i]) * moduleWidth;
      if (i % 2 === 0) bars += `<rect x="${x}" y="0" width="${w}" height="${height}" fill="#000"/>`;
      x += w;
    }
  }
  const width = x + 10;
  const label = showText
    ? `<text x="${width / 2}" y="${height + 14}" font-family="monospace" font-size="12" text-anchor="middle" fill="#000">${escapeXml(text)}</text>`
    : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height + (showText ? 18 : 0)}" viewBox="0 0 ${width} ${height + (showText ? 18 : 0)}">${bars}${label}</svg>`;
}

function escapeXml(s) {
  return String(s).replace(/[<>&'"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", "'": "&apos;", '"': "&quot;" }[c]));
}
