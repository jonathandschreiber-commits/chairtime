import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = path.resolve("frontend/app/api/shops");
const files = [];
function walk(dir) {
  for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, item.name);
    if (item.isDirectory()) walk(full);
    else if (item.name === "route.js") files.push(full);
  }
}
walk(root);

test("every shop API route avoids any hard-coded production backend", () => {
  assert.ok(files.length >= 19, "Expected shop API routes");
  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");
    assert.doesNotMatch(source, /chairtime-production-94da\.up\.railway\.app/,
      `${path.relative(root, file)} still routes to production`);
  }
});

test("every shop API route uses the scoped backend selector", () => {
  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");
    assert.match(source, /serverApiBase/,
      `${path.relative(root, file)} does not use the scoped backend selector`);
  }
});

test("shop hours rules expose a DELETE handler", () => {
  const file = path.join(root,
    "[shopSlug]/shop-availability-rules/[ruleId]/route.js");
  const source = fs.readFileSync(file, "utf8");
  assert.match(source, /export async function DELETE/);
  assert.match(source, /method: "DELETE"/);
  assert.match(source, /serverApiBase\(\)/);
});
