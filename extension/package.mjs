// Packs the built extension (dist/) for the Chrome Web Store: iplikci-kopru-<version>.zip beside this file, the
// built files at its root as the store wants them. The release workflow uploads it (ADR-0022); the first version is
// uploaded by hand from the store's developer dashboard. A manifest with a "key" field is refused: the store sets the
// extension's key itself.
import { execFileSync } from "node:child_process";
import { readFileSync, rmSync } from "node:fs";

const { version } = JSON.parse(readFileSync("package.json", "utf8"));
const manifest = JSON.parse(readFileSync("dist/manifest.json", "utf8"));
if (manifest.version !== version) {
  throw new Error(`dist/manifest.json ${manifest.version} sürümünde, package.json ${version}: önce npm run build`);
}
if ("key" in manifest) {
  throw new Error("Mağaza paketi \"key\" alanı taşıyamaz");
}
const name = `iplikci-kopru-${version}.zip`;
rmSync(name, { force: true });
execFileSync("zip", ["-qrX", `../${name}`, "."], { cwd: "dist", stdio: "inherit" });
console.log(name);
