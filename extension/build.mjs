// Builds the extension into dist/: the service worker and the page bundled by esbuild, the manifest with the
// package's version, and the static files. The bundles stay readable (no minification): a store review and the
// user can read what the extension does.
import { build } from "esbuild";
import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";

const pkg = JSON.parse(await readFile("package.json", "utf8"));
await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });
await build({
  entryPoints: { background: "src/background.ts", verify: "src/verify/page.ts" },
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
for (const file of ["verify.html", "verify.css"]) {
  await cp(`static/${file}`, `dist/${file}`);
}
