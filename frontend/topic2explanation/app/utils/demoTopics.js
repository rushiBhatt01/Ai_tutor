// Demo topics available in the local cache
// These topics have pre-generated videos in the frontend/prev_videos folder
export const DEMO_TOPICS = [
  "agentic ai",
  "Ai Engineer",
  "Ai Engineer3",
  "AI",
  "BFS",
  "binary search",
  "binary sorting",
  "blockchain",
  "Crypto",
  "Data science",
  "DDOS",
  "deep brain stimulation using ai using contents from IEEE spectrum only",
  "deep brain stimulation using ai",
  "DEEP LEARNING",
  "DFS",
  "digital forensics",
  "Dijkstra algorithm",
  "Explain OAuth 2.0",
  "Game theory",
  "gui",
  "health care applicaation using machine learning",
  "how ai helps in deep brain stimulation",
  "IDE",
  "Intro to Machine Learning",
  "Introduction to APIs",
  "KV caching",
  "linear regression",
  "linear sort",
  "microprocessor",
  "music assistant",
  "Networking devices",
  "NEURAL NETWORK",
  "NoSQL",
  "open knowledge graph",
  "playwright",
  "Retrieval Augmented Generation (RAG)",
  "robotics",
  "Robotics",
  "solar system",
  "System Design",
  "virtual reality",
  "VR",
];

/**
 * Normalize topic name for file path comparison
 * This handles case-insensitivity, whitespace trimming, and .mp4 extensions
 */
export const normalizeTopicForCache = (topic) => {
  if (!topic) return "";
  let clean = topic.trim().toLowerCase();
  if (clean.endsWith(".mp4")) {
    clean = clean.slice(0, -4).trim();
  }
  return clean.replace(/\s+/g, " ");
};

/**
 * Strip non-alphanumeric characters for fuzzy matching across punctuation variations
 */
export const toAlphanumericKey = (topic) => {
  if (!topic) return "";
  return topic.toLowerCase().replace(/[^a-z0-9]/g, "");
};

/**
 * Match topic against DEMO_TOPICS using:
 * 1. Normalized comparison (case-insensitive, trimmed, stripped .mp4)
 * 2. Alphanumeric comparison (ignores punctuation like parentheses, dots, hyphens)
 */
export const findMatchingDemoTopic = (topic) => {
  if (!topic) return null;
  const normalized = normalizeTopicForCache(topic);
  if (!normalized) return null;

  const exactMatch = DEMO_TOPICS.find(
    (t) => normalizeTopicForCache(t) === normalized
  );
  if (exactMatch) return exactMatch;

  const alphaKey = toAlphanumericKey(topic);
  return (alphaKey && DEMO_TOPICS.find(
    (t) => toAlphanumericKey(t) === alphaKey
  )) || null;
};

/**
 * Check if a topic exists in the demo topics list
 */
export const isDemoTopic = (topic) => {
  return findMatchingDemoTopic(topic) !== null;
};

/**
 * Get the exact filename for a demo topic
 */
export const getDemoTopicFilename = (topic) => {
  const found = findMatchingDemoTopic(topic);
  return found ? `${found}.mp4` : null;
};
