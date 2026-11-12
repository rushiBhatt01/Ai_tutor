import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("./demoTopics.js", import.meta.url), "utf8");
const { DEMO_TOPICS, findMatchingDemoTopic, getDemoTopicFilename, isDemoTopic } =
  await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

test("all demo topics preserve exact matching and filenames", () => {
  for (const topic of DEMO_TOPICS) {
    const expected = DEMO_TOPICS.find(t => t.toLowerCase() === topic.toLowerCase());
    assert.equal(findMatchingDemoTopic(`  ${topic.toUpperCase()}.mp4  `), expected);
    assert.equal(getDemoTopicFilename(topic), `${expected}.mp4`);
    assert.equal(isDemoTopic(topic), true);
  }
});

test("punctuation fallback and cache misses retain their results", () => {
  assert.equal(findMatchingDemoTopic("Explain OAuth 2.0."), "Explain OAuth 2.0");
  assert.equal(findMatchingDemoTopic("retrieval augmented generation rag"), "Retrieval Augmented Generation (RAG)");
  for (const topic of [null, undefined, "", "  ", "???", "unknown topic", "Explain OAuth 2.0!.mp4"]) {
    assert.equal(findMatchingDemoTopic(topic), null);
    assert.equal(getDemoTopicFilename(topic), null);
    assert.equal(isDemoTopic(topic), false);
  }
});
