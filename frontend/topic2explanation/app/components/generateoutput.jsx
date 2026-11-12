import { PIPELINE_STEPS } from "./PipelineProgress";
import { resolveCachedVideoUrl } from "../utils/cacheUtil";
import { backendUrl } from "../utils/backendUrl";

export const generateOutput = async (
  message,
  level,
  age,
  creative,
  humour,
  characterName,
  setLoading,
  setVideoUrl,
  enableSubtitles = false
) => {
  try {
    // 1. Check if a video for this topic already exists in prev_videos
    const cachedUrl = await resolveCachedVideoUrl(message);

    // Compute pipeline total duration (ms) for the progress animation
    const pipelineDuration = PIPELINE_STEPS.reduce((s, step) => s + (step.duration || 0), 0);

    // If cached video exists, simulate the pipeline progress animation then load from prev_videos
    if (cachedUrl) {
      console.log(`✓ Cached video found in prev_videos for "${message}": ${cachedUrl}`);
      
      // Wait for all pipeline steps to complete so user sees the generation animation
      await new Promise((resolve) => setTimeout(resolve, pipelineDuration));
      
      console.log(`✓ Pipeline complete. Loading cached video for "${message}"...`);
      setVideoUrl(cachedUrl);
      console.log("✓ Successfully loaded video from prev_videos:", cachedUrl);
      setLoading(false);
      return;
    }

    // 2. If not found in prev_videos, attempt backend pipeline generation
    console.warn(`✗ Topic "${message}" not in prev_videos cache. Attempting backend generation...`);

    const headers = new Headers();
    headers.append("Content-Type", "application/json");
    if (process.env.NODE_ENV === "development") {
      headers.append("Authorization", "Basic " + btoa("myusername:mypassword"));
    }

    // Add small buffer (500ms) to backend request
    const totalPipelineMs = pipelineDuration + 500;

    const body = JSON.stringify({
      message,
      level,
      age,
      creative,
      humour,
      characterName,
      enableSubtitles,
      pipelineDelayMs: totalPipelineMs,
    });

    const response = await fetch(backendUrl("/videoCreate"), {
      method: "POST",
      body: body,
      headers: headers,
    });

    if (response.status === 202) {
      const job = await response.json();
      // The browser's existing Basic session authenticates same-origin polls.
      const deadline = Date.now() + 2 * 60 * 60 * 1000;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const statusResponse = await fetch(backendUrl(`/api/jobs/${job.job_id}`));
        if (!statusResponse.ok) throw new Error("Could not read lesson progress");
        const status = await statusResponse.json();
        if (status.status === "FAILED") throw new Error(`Lesson generation failed: ${status.error || "unknown error"}`);
        if (status.status === "COMPLETED") {
          setVideoUrl(backendUrl(status.video_url));
          return;
        }
      }
      throw new Error("Lesson is still processing. Check its status before submitting again.");
    } else if (response.ok) {
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
