// Adds the permissions the Chesstor phone app needs to the generated Android manifest (idempotent).
// Usage: npx cap add android && node scripts/android-prepare.mjs
import { readFileSync, writeFileSync, existsSync } from "node:fs";

const path = "android/app/src/main/AndroidManifest.xml";
if (!existsSync(path)) {
  console.error("Run `npx cap add android` first.");
  process.exit(1);
}
let xml = readFileSync(path, "utf8");
const add = [
  '<uses-permission android:name="android.permission.CAMERA" />',
  '<uses-feature android:name="android.hardware.camera" android:required="false" />',
];
let changed = false;
for (const line of add) {
  if (!xml.includes(line.split(" ").slice(0, 2).join(" ") + " " + line.split(" ")[2])) {
    xml = xml.replace("</manifest>", `    ${line}\n</manifest>`);
    changed = true;
  }
}
writeFileSync(path, xml);
console.log(changed ? "Manifest patched: CAMERA permission added." : "Manifest already patched.");
