// Invoke JavaScript entry points directly: Windows .cmd shims misparse an ampersand in paths.
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
for (const [entry, args] of [
  ["typescript/bin/tsc", ["-b"]],
  ["vite/bin/vite.js", ["build"]],
]) {
  const result = spawnSync(
    process.execPath,
    [path.join(root, "node_modules", entry), ...args],
    {
      cwd: root,
      stdio: "inherit",
      shell: false,
    },
  );
  if (result.status !== 0) process.exit(result.status ?? 1);
}
