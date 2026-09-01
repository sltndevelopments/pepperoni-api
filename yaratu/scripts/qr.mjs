import { readFile } from "node:fs/promises";
import { SITE } from "./lib.mjs";

export function qrUrl(id) {
  return `${SITE}/q/${id}`;
}

export function qrPath(id) {
  return `/q/${id}/`;
}

export async function qrSvg(id) {
  const svg = await readFile(new URL(`../assets/qr/${id}.svg`, import.meta.url), "utf8");
  if (!svg.includes(qrUrl(id))) throw new Error(`QR asset ${id} does not encode ${qrUrl(id)}`);
  return svg.trim();
}
