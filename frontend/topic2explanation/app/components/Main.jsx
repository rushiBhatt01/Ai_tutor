// main.jsx
"use client";
import React from "react";
import { useState, useEffect } from "react";
import Box1 from "./box1";
import Box2 from "./box2";
import VideoHistory from "./VideoHistory";
import { generateOutput } from "./generateoutput";

export default function Main() {
  const [message, setMessage] = useState("");
  const [level, setLevel] = useState("beginner");
  const [age, setAge] = useState(18);
  const [creative, setCreative] = useState(8);
  const [humour, setHumour] = useState(6);
  const [characterName, setCharacterName] = useState("Benjamin");
  const [loading, setLoading] = useState(false);
  const [videoUrl, setVideoUrl] = useState("");

  useEffect(() => {
    if (loading) {
      generateOutput(
        message,
        level,
        age,
        creative,
        humour,
        characterName,
        setLoading,
        setVideoUrl
      );
    }
  }, [age, characterName, creative, humour, level, loading, message]);

  const handleHistorySelect = (url) => {
    setVideoUrl(url);
  };

  return (
    <div className="studio-layout">
      <div className="studio-main">
        <Box1
          message={message}
          setMessage={setMessage}
          level={level}
          age={age}
          creative={creative}
          humour={humour}
          characterName={characterName}
          loading={loading}
          setLoading={setLoading}
          videoUrl={videoUrl}
        />
        <VideoHistory
          currentVideoUrl={videoUrl}
          currentTopic={message}
          onSelect={handleHistorySelect}
        />
      </div>
      <aside className="studio-sidebar">
        <Box2
          level={level}
          setLevel={setLevel}
          age={age}
          setAge={setAge}
          creative={creative}
          setCreative={setCreative}
          humour={humour}
          setHumour={setHumour}
          characterName={characterName}
          setCharacterName={setCharacterName}
        />
      </aside>
    </div>
  );
}
