"use client";

import { useEffect, useRef, useState } from "react";

const phrases = [
  "polished tutorial video",
  "visual learning experience",
  "AI-powered walkthrough",
  "engaging explainer video",
];

export default function TypingEffect() {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [text, setText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const timeoutRef = useRef(null);

  useEffect(() => {
    const currentPhrase = phrases[phraseIndex];

    const tick = () => {
      if (!isDeleting) {
        // Typing forward
        const next = currentPhrase.slice(0, text.length + 1);
        setText(next);

        if (next === currentPhrase) {
          // Pause at full phrase, then start deleting
          timeoutRef.current = setTimeout(() => setIsDeleting(true), 2200);
          return;
        }
        timeoutRef.current = setTimeout(tick, 70 + Math.random() * 40);
      } else {
        // Deleting
        const next = currentPhrase.slice(0, text.length - 1);
        setText(next);

        if (next === "") {
          setIsDeleting(false);
          setPhraseIndex((prev) => (prev + 1) % phrases.length);
          timeoutRef.current = setTimeout(tick, 400);
          return;
        }
        timeoutRef.current = setTimeout(tick, 35);
      }
    };

    timeoutRef.current = setTimeout(tick, isDeleting ? 35 : 100);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [text, isDeleting, phraseIndex]);

  return (
    <span className="typing-effect">
      <span className="text-gradient">{text}</span>
      <span className="typing-cursor" aria-hidden="true">
        |
      </span>
    </span>
  );
}
