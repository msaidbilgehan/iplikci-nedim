// Builds the extension into dist/: the service worker and the page bundled by esbuild, the manifest with the
// package's version, and the static files. The bundles stay readable (no minification): a store review and the
// user can read what the extension does. The program carries a copy (src/iplikci/browser_extension), which the
// service puts in the data folder for the browser to load unpacked until the extension is in a store (K20).
import { build } from "esbuild";
import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";

const pkg = JSON.parse(await readFile("package.json", "utf8"));
await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });
await build({
  entryPoints: { background: "src/background.ts", verify: "src/verify/page.ts", options: "src/options/page.ts" },
  bundle: true,
  format: "esm",
  target: "chrome120",
  outdir: "dist",
  legalComments: "none",
  logLevel: "warning",
});
const manifest = JSON.parse(await readFile("static/manifest.json", "utf8"));
manifest.version = pkg.version;
await writeFile("dist/manifest.json", `${JSON.stringify(manifest, null, 2)}\n`);
for (const file of ["verify.html", "verify.css", "options.html"]) {
  await cp(`static/${file}`, `dist/${file}`);
}
await cp("static/icons", "dist/icons", { recursive: true }); // drawn by tools/icons.py
const carried = "../src/iplikci/browser_extension";
await rm(carried, { recursive: true, force: true });
await cp("dist", carried, { recursive: true });
