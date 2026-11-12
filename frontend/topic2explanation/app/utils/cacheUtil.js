import { getDemoTopicFilename } from "./demoTopics";
import { backendUrl } from "./backendUrl";

/**
 * Resolve a cached video URL if it exists in prev_videos.
 * Checks:
 * 1. Demo topics lookup (instant, case-insensitive, punctuation-tolerant)
 * 2. Static directory check via HEAD request
 * 3. Backend checkVideoCache API endpoint (if backend is active)
 */
export const resolveCachedVideoUrl = async (topic) => {
  if (!topic || !topic.trim()) return null;

  // 1. Try known demo topics list
  const filename = getDemoTopicFilename(topic);
  if (filename) {
    return `/prev_videos/${encodeURIComponent(filename)}`;
  }

  const clean = topic.trim().replace(/\.mp4$/i, "");

  // 2. Try direct static fetch with HEAD request
  if (typeof window !== "undefined") {
    try {
      const candidateUrl = `/prev_videos/${encodeURIComponent(clean + ".mp4")}`;
      const res = await fetch(candidateUrl, { method: "HEAD" });
      if (res.ok) return candidateUrl;
    } catch {
      // Ignore static fetch errors
    }

    // 3. Try backend checkVideoCache endpoint
    try {
      const cacheUrl = backendUrl(`/checkVideoCache/${encodeURIComponent(clean)}`);
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 1500);

      const res = await fetch(cacheUrl, { signal: controller.signal });
      clearTimeout(timeoutId);

      if (res.ok) {
        const data = await res.json();
        if (data && data.exists && data.filename) {
          return `/prev_videos/${encodeURIComponent(data.filename)}`;
        }
      }
    } catch {
      // Backend offline or unreachable
    }
  }

  return null;
};

/**
 * Check if a cached video exists for the given topic
 */
export const checkCachedVideoExists = async (topic) => {
  try {
    return Boolean(await resolveCachedVideoUrl(topic));
  } catch (error) {
    console.warn(`Failed to check cached video for topic "${topic}":`, error);
    return false;
  }
};

/**
 * Load a cached video directly from the frontend/prev_videos folder
 * Returns a static URL for direct progressive streaming
 */
export const loadCachedVideo = async (topic) => {
  const url = await resolveCachedVideoUrl(topic);
  if (!url) {
    throw new Error(`No cached video found for topic: ${topic}`);
  }
  return url;
};

/**
 * Try to load from cache, fall back to backend if needed
 */
export const getVideoUrl = async (topic, backendFetcher) => {
  try {
    const cachedUrl = await resolveCachedVideoUrl(topic);
    if (cachedUrl) {
      console.log(`✓ Loading cached video for topic "${topic}": ${cachedUrl}`);
      return cachedUrl;
    }
  } catch (error) {
    console.warn(`Failed to check cached video for topic "${topic}":`, error);
  }

  console.log(`✗ No cached video for topic: ${topic}. Attempting backend request...`);
  return await backendFetcher();
};
