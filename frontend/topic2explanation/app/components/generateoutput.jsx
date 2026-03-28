import { PIPELINE_STEPS } from "./PipelineProgress";
import { isDemoTopic } from "../utils/demoTopics";
import { loadCachedVideo } from "../utils/cacheUtil";

export const generateOutput = async (
  message,
  level,
  age,
  creative,
  humour,
  characterName,
  setLoading,
  setVideoUrl
) => {
  try {
    const demoTopic = isDemoTopic(message);

    // Compute pipeline total duration (ms)
    const pipelineDuration = PIPELINE_STEPS.reduce((s, step) => s + (step.duration || 0), 0);

    // If it's a demo topic, wait for pipeline to complete then load from cache
    if (demoTopic) {
      console.log(`✓ Demo topic detected: "${message}". Waiting for pipeline steps to complete...`);
      
      // Wait for all pipeline steps to complete
      await new Promise((resolve) => setTimeout(resolve, pipelineDuration));
      
      try {
        console.log(`✓ Pipeline complete. Loading cached video for "${message}"...`);
        const cachedUrl = await loadCachedVideo(message);
        setVideoUrl(cachedUrl);
        console.log("✓ Successfully loaded from cache");
        setLoading(false);
        return;
      } catch (cacheError) {
        console.warn("Failed to load from cache:", cacheError);
        setLoading(false);
        alert(`Error loading demo video: ${cacheError.message}`);
        return;
      }
    }

    // If not a demo topic, show warning and attempt backend
    console.warn(`✗ Topic "${message}" not available offline. Attempting backend request...`);

    const headers = new Headers();
    headers.append("Content-Type", "application/json");
    headers.append("Authorization", "Basic " + btoa("myusername:mypassword"));

    // Add small buffer (500ms) to backend request
    const totalPipelineMs = pipelineDuration + 500;

    const body = JSON.stringify({
      message,
      level,
      age,
      creative,
      humour,
      characterName,
      pipelineDelayMs: totalPipelineMs,
    });

    const response = await fetch("http://127.0.0.1:8000/videoCreate", {
      method: "POST",
      body: body,
      headers: headers,
    });

    if (response.ok) {
      const blob = await response.blob();
      const videoUrl = URL.createObjectURL(blob);
      setVideoUrl(videoUrl);
      console.log("✓ Successfully generated video from backend");
    } else {
      console.error("Backend error:", response.statusText);
      alert(`Failed to generate video. Backend responded with: ${response.statusText}`);
    }
  } catch (error) {
    console.error("Error during video generation:", error);
    alert(`Error: ${error.message}`);
  } finally {
    setLoading(false);
  }
};
