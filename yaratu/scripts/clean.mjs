import { rm } from "node:fs/promises";

await rm(new URL("../site/dist", import.meta.url), { recursive: true, force: true });
console.log("Cleaned site/dist");
