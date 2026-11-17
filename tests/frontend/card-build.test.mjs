import assert from "node:assert/strict";
import {
  cp,
  mkdtemp,
  mkdir,
  readFile,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

test("build check rejects a stale bundle without overwriting it", async () => {
  const root = fileURLToPath(new URL("../../", import.meta.url));
  const fixture = await mkdtemp(join(tmpdir(), "pixelit-card-build-"));
  try {
    await mkdir(join(fixture, "scripts"));
    await mkdir(join(fixture, "custom_components/pixelit/www"), {
      recursive: true,
    });
    await cp(join(root, "src"), join(fixture, "src"), { recursive: true });
    await cp(
      join(root, "scripts/build-card.mjs"),
      join(fixture, "scripts/build-card.mjs"),
    );
    await symlink(
      join(root, "node_modules"),
      join(fixture, "node_modules"),
      "junction",
    );
    const output = join(
      fixture,
      "custom_components/pixelit/www/pixelit-card.js",
    );
    const script = join(fixture, "scripts/build-card.mjs");
    const build = (...args) =>
      spawnSync(process.execPath, [script, ...args], {
        cwd: fixture,
        encoding: "utf8",
      });
    const generated = build();
    assert.equal(generated.status, 0, generated.stderr);
    const matching = build("--check");
    assert.equal(matching.status, 0, matching.stderr);
    const stale = (await readFile(output, "utf8")) + "\n// Stale manual edit\n";
    await writeFile(output, stale);
    const rejected = build("--check");
    assert.notEqual(rejected.status, 0);
    assert.match(rejected.stderr, /Shipped card differs from source/);
    assert.equal(await readFile(output, "utf8"), stale);
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});
