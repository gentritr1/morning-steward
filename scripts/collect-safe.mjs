import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const node = process.execPath;
const cleanArgs = process.argv.includes("--dry-run") ? ["--dry-run"] : [];
const environment = { ...process.env, STEWARD_AUTO_CLEAN_SAFE: "1" };

function run(script, args = []) {
  return new Promise((resolve, reject) => {
    const child = spawn(node, [path.join(projectRoot, "scripts", script), ...args], {
      cwd: projectRoot,
      env: environment,
      stdio: "inherit",
    });
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code === 0) resolve();
      else reject(new Error(`${script} exited with ${signal ? `signal ${signal}` : `code ${code}`}`));
    });
  });
}

await run("collect-storage.mjs");
await run("cleanup-safe.mjs", cleanArgs);
await run("collect-storage.mjs");
