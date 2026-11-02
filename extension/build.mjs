// Builds the extension into dist/: the service worker and the pages' scripts bundled by esbuild (the window from the
// toolbar button, the settings page and the verification page), the manifest with the package's version, and the
// static files. The bundles stay readable (no minification): a store review and the user can read what the extension
// does. The program carries a copy (src/iplikci/browser_extension), which the service puts in the data folder for the
// browser to load unpacked until the extension is in a store (K20).
//
// Everything is built in a folder of its own (.yapim-*) and each result takes the old one's place whole: a build that
// fails or is cut short never leaves dist/ or the program's copy half written, and the service copies the program's
// copy into the data folder as it finds it.
import { build } from "esbuild";
import { cp, mkdir, mkdtemp, readdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";

const WORK = ".yapim-";
const pkg = JSON.parse(await readFile("package.json", "utf8"));
for (const name of await readdir(".")) {
  if (name.startsWith(WORK)) {
    await rm(name, { recursive: true, force: true }); // what a build cut short left
  }
}
const work = await mkdtemp(WORK); // beside dist/ and the program: a rename moves the result into place at once
try {
  const fresh = join(work, "dist");
  await mkdir(fresh);
  await build({
    entryPoints: {
      background: "src/background.ts",
      popup: "src/popup/page.ts",
      options: "src/options/page.ts",
      verify: "src/verify/page.ts",
    },
    bundle: true,
    format: "esm",
    target: "chrome120",
    outdir: fresh,
    legalComments: "none",
    logLevel: "warning",
  });
  const manifest = JSON.parse(await readFile("static/manifest.json", "utf8"));
  manifest.version = pkg.version;
  await writeFile(join(fresh, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  for (const file of ["popup.html", "options.html", "verify.html", "style.css"]) {
    await cp(join("static", file), join(fresh, file));
  }
  await cp(join("static", "icons"), join(fresh, "icons"), { recursive: true }); // from the logo: packaging/icons.py
  const carried = join(work, "carried");
  await cp(fresh, carried, { recursive: true });
  await replace("dist", fresh, join(work, "old-dist"));
  await replace(join("..", "src", "iplikci", "browser_extension"), carried, join(work, "old-carried"));
} finally {
  await rm(work, { recursive: true, force: true });
}

/** Put `fresh` where `target` is: the old one moves aside first, so `target` is always one whole build or none. */
async function replace(target, fresh, aside) {
  try {
    await rename(target, aside);
  } catch (error) {
    if (error.code !== "ENOENT") {
      throw error;
    }
  }
  await rename(fresh, target);
}
