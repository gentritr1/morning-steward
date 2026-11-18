import { access, lstat, readFile, rm, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";

const execFileAsync = promisify(execFile);
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dataRoot = path.join(projectRoot, "public", "data");
const eventsPath = path.join(dataRoot, "events.json");
const userHome = os.homedir();
const projectsRoot = path.join(userHome, "Desktop", "Projects");

const GLOBAL_SAFE_TARGETS = [
  { id: "gradle-cache", label: "Gradle dependency cache", targetPath: path.join(userHome, ".gradle", "caches") },
  { id: "gradle-cache", label: "Gradle dependency cache", targetPath: path.join(userHome, ".gradle", ".tmp") },
  { id: "npm-cache", label: "npm and npx cache", targetPath: path.join(userHome, ".npm", "_cacache") },
  { id: "npm-cache", label: "npm and npx cache", targetPath: path.join(userHome, ".npm", "_npx") },
  { id: "xcode-derived", label: "Xcode Derived Data", targetPath: path.join(userHome, "Library", "Developer", "Xcode", "DerivedData") },
];

const PROJECT_TARGET_KINDS = new Map([
  ["android-build", { id: "android-builds", label: "Android build outputs" }],
  ["project-gradle", { id: "project-gradle", label: "Project-local Gradle caches" }],
  ["unity-library", { id: "unity-libraries", label: "Unity-generated libraries" }],
]);

function formatBytes(value) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = Math.max(0, Number(value) || 0);
  let unitIndex = 0;

  while (amount >= 1024 && unitIndex < units.length - 1) {
    amount /= 1024;
    unitIndex += 1;
  }

  const digits = amount >= 100 || unitIndex === 0 ? 0 : 1;
  return `${new Intl.NumberFormat("en", { maximumFractionDigits: digits }).format(amount)} ${units[unitIndex]}`;
}

async function commandOutput(command, args) {
  try {
    const result = await execFileAsync(command, args, {
      encoding: "utf8",
      maxBuffer: 32 * 1024 * 1024,
      timeout: 180_000,
    });
    return result.stdout.trim();
  } catch (error) {
    if (typeof error?.stdout === "string" && error.stdout.trim()) return error.stdout.trim();
    return "";
  }
}

async function pathExists(targetPath) {
  try {
    await access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function directoryBytes(targetPath) {
  if (!(await pathExists(targetPath))) return 0;
  const output = await commandOutput("du", ["-sk", targetPath]);
  const kibibytes = Number.parseInt(output.split(/\s+/)[0] ?? "0", 10);
  return Number.isFinite(kibibytes) ? kibibytes * 1024 : 0;
}

async function findDirectories(rootPath, args) {
  if (!(await pathExists(rootPath))) return [];
  const output = await commandOutput("find", [rootPath, ...args]);
  return output ? output.split("\n").filter(Boolean) : [];
}

function isInside(rootPath, targetPath) {
  const relative = path.relative(rootPath, targetPath);
  return relative !== "" && !relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative);
}

async function projectTargets() {
  const [androidBuildCandidates, gradleHomes, libraryCandidates] = await Promise.all([
    findDirectories(projectsRoot, ["-type", "d", "-path", "*/android/app/build", "-prune", "-print"]),
    findDirectories(projectsRoot, ["-type", "d", "-name", ".gradle-user-home", "-prune", "-print"]),
    findDirectories(projectsRoot, ["-type", "d", "-name", "Library", "-prune", "-print"]),
  ]);

  const targets = [];
  const androidBuilds = androidBuildCandidates.filter(
    (targetPath) => !targetPath.includes(`${path.sep}.cxx${path.sep}`),
  );
  for (const targetPath of androidBuilds) {
    targets.push({ ...PROJECT_TARGET_KINDS.get("android-build"), targetPath });
  }
  for (const targetPath of gradleHomes) {
    targets.push({ ...PROJECT_TARGET_KINDS.get("project-gradle"), targetPath });
  }
  for (const targetPath of libraryCandidates) {
    const versionFile = path.join(path.dirname(targetPath), "ProjectSettings", "ProjectVersion.txt");
    if (await pathExists(versionFile)) {
      targets.push({ ...PROJECT_TARGET_KINDS.get("unity-library"), targetPath });
    }
  }
  return targets;
}

async function collectSafeTargets() {
  const candidates = [...GLOBAL_SAFE_TARGETS, ...(await projectTargets())];
  const seen = new Set();
  const targets = [];

  for (const candidate of candidates) {
    const targetPath = path.resolve(candidate.targetPath);
    if (seen.has(targetPath)) continue;
    seen.add(targetPath);

    const isGlobalTarget = GLOBAL_SAFE_TARGETS.some((item) => item.targetPath === targetPath);
    if (!isGlobalTarget && !isInside(projectsRoot, targetPath)) {
      throw new Error(`Refusing target outside the project root: ${targetPath}`);
    }

    let info;
    try {
      info = await lstat(targetPath);
    } catch (error) {
      if (error?.code === "ENOENT") continue;
      throw error;
    }

    if (info.isSymbolicLink()) throw new Error(`Refusing symbolic-link target: ${targetPath}`);
    if (!info.isDirectory()) throw new Error(`Refusing non-directory target: ${targetPath}`);

    targets.push({ ...candidate, targetPath, bytes: await directoryBytes(targetPath) });
  }

  return targets.filter((target) => target.bytes > 0);
}

async function appendEvent(targets) {
  if (targets.length === 0) return;

  let eventsData = { schemaVersion: 1, events: [] };
  try {
    eventsData = JSON.parse(await readFile(eventsPath, "utf8"));
  } catch {
    /* A missing or malformed event file should not block a safe cleanup. */
  }

  const grouped = new Map();
  for (const target of targets) {
    const current = grouped.get(target.id) ?? { label: target.label, bytes: 0, count: 0 };
    current.bytes += target.bytes;
    current.count += 1;
    grouped.set(target.id, current);
  }

  const details = [...grouped.values()].map(
    (group) => `${group.label}: ${formatBytes(group.bytes)} across ${group.count} target${group.count === 1 ? "" : "s"}.`,
  );
  details.push("Review-only categories were left untouched.");

  const event = {
    occurredAt: new Date().toISOString(),
    type: "cleanup",
    title: "Safe rebuildable data cleared",
    summary: `Steward removed ${formatBytes(targets.reduce((sum, target) => sum + target.bytes, 0))} from its approved safe allowlist after the local scan.`,
    reclaimedBytes: targets.reduce((sum, target) => sum + target.bytes, 0),
    details,
  };

  const events = Array.isArray(eventsData.events) ? eventsData.events : [];
  await writeFile(eventsPath, `${JSON.stringify({ ...eventsData, schemaVersion: 1, events: [event, ...events] }, null, 2)}\n`, "utf8");
}

const dryRun = process.argv.includes("--dry-run");
const targets = await collectSafeTargets();
const reclaimedBytes = targets.reduce((sum, target) => sum + target.bytes, 0);

if (!dryRun) {
  for (const target of targets) {
    const info = await lstat(target.targetPath);
    if (info.isSymbolicLink() || !info.isDirectory()) {
      throw new Error(`Target changed during cleanup: ${target.targetPath}`);
    }
    await rm(target.targetPath, { recursive: true, force: true });
  }
  await appendEvent(targets);
}

console.log(JSON.stringify({
  mode: dryRun ? "dry-run" : "cleanup",
  targets: targets.map(({ id, label, targetPath, bytes }) => ({ id, label, targetPath, bytes })),
  reclaimedBytes: dryRun ? 0 : reclaimedBytes,
}, null, 2));
