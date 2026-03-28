// Demo topics available in the local cache
// These topics have pre-generated videos in the frontend/prev_videos folder
export const DEMO_TOPICS = [
  "agentic ai",
  "Ai Engineer",
  "Ai Engineer3",
  "AI",
  "blockchain",
  "Crypto",
  "Data science",
  "DDOS",
  "deep brain stimulation using ai using contents from IEEE spectrum only",
  "deep brain stimulation using ai",
  "DEEP LEARNING",
  "digital forensics",
  "Explain OAuth 2.0",
  "Game theory",
  "gui",
  "health care applicaation using machine learning",
  "how ai helps in deep brain stimulation",
  "IDE",
  "Intro to Machine Learning",
  "Introduction to APIs",
  "microprocessor",
  "Networking devices",
  "NEURAL NETWORK",
  "solar system",
  "virtual reality",
  "VR",
];

/**
 * Normalize topic name for file path comparison
 * This handles case-insensitivity and filename conventions
 */
export const normalizeTopicForCache = (topic) => {
  return topic.toLowerCase().trim();
};

/**
 * Check if a topic exists in the demo topics list
 */
export const isDemoTopic = (topic) => {
  const normalized = normalizeTopicForCache(topic);
  return DEMO_TOPICS.some((t) => normalizeTopicForCache(t) === normalized);
};

/**
 * Get the exact filename for a demo topic
 */
export const getDemoTopicFilename = (topic) => {
  const normalized = normalizeTopicForCache(topic);
  const found = DEMO_TOPICS.find((t) => normalizeTopicForCache(t) === normalized);
  return found ? `${found}.mp4` : null;
};
