import { getDemoTopicFilename } from "./demoTopics";

/**
 * Check if a cached video exists for the given topic
 * by attempting to fetch it from the frontend/prev_videos folder
 */
export const checkCachedVideoExists = async (topic) => {
  try {
    const filename = getDemoTopicFilename(topic);
    if (!filename) {
      return false;
    }

    // Try to fetch the video with a HEAD request (or GET with minimal data)
    const response = await fetch(`/prev_videos/${filename}`, {
      method: "HEAD",
    });
    return response.ok;
  } catch (error) {
    console.warn(`Failed to check cached video for topic "${topic}":`, error);
    return false;
  }
};

/**
 * Load a cached video directly from the frontend/prev_videos folder
 * Returns a blob URL that can be used as src for <video>
 */
export const loadCachedVideo = async (topic) => {
  try {
    const filename = getDemoTopicFilename(topic);
    if (!filename) {
      throw new Error(`No cached video found for topic: ${topic}`);
    }

    const response = await fetch(`/prev_videos/${filename}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch cached video: ${response.statusText}`);
    }

    const blob = await response.blob();
    const videoUrl = URL.createObjectURL(blob);
    return videoUrl;
  } catch (error) {
    console.error(`Error loading cached video for topic "${topic}":`, error);
    throw error;
  }
};

/**
 * Try to load from cache, fall back to backend if needed
 */
export const getVideoUrl = async (topic, backendFetcher) => {
  try {
    // First, try to load from cache
    const exists = await checkCachedVideoExists(topic);
    if (exists) {
      console.log(`✓ Loading cached video for topic: ${topic}`);
      return await loadCachedVideo(topic);
    }
  } catch (error) {
    console.warn(`Failed to load cached video for topic "${topic}":`, error);
  }

  // If not in cache, try backend
  console.log(`✗ No cached video for topic: ${topic}. Attempting backend request...`);
  return await backendFetcher();
};
