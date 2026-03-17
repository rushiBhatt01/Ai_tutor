"use client";

import { useEffect, useRef, useState } from "react";

export default function GlowCursor() {
  const dotRef = useRef(null);
  const trailRefs = useRef([]);
  const [isDesktop, setIsDesktop] = useState(false);
  const pos = useRef({ x: -100, y: -100 });
  const trail = useRef(
    Array.from({ length: 5 }, () => ({ x: -100, y: -100 }))
  );

  useEffect(() => {
    const isPointerFine = window.matchMedia("(pointer: fine)").matches;
    setIsDesktop(isPointerFine);
    if (!isPointerFine) return;

    const onMove = (e) => {
      pos.current = { x: e.clientX, y: e.clientY };
    };

    let raf;
    const animate = () => {
      // Move trail points
      trail.current.forEach((pt, i) => {
        const target = i === 0 ? pos.current : trail.current[i - 1];
        pt.x += (target.x - pt.x) * (0.35 - i * 0.04);
        pt.y += (target.y - pt.y) * (0.35 - i * 0.04);
      });

      if (dotRef.current) {
        dotRef.current.style.transform = `translate(${pos.current.x}px, ${pos.current.y}px)`;
      }

      trailRefs.current.forEach((el, i) => {
        if (el) {
          el.style.transform = `translate(${trail.current[i].x}px, ${trail.current[i].y}px)`;
        }
      });

      raf = requestAnimationFrame(animate);
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    raf = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  if (!isDesktop) return null;

  return (
    <div className="glow-cursor-container" aria-hidden="true">
      {trail.current.map((_, i) => (
        <div
          key={i}
          className="glow-cursor-trail"
          ref={(el) => (trailRefs.current[i] = el)}
          style={{
            width: `${7 - i}px`,
            height: `${7 - i}px`,
            opacity: 0.4 - i * 0.07,
          }}
        />
      ))}
      <div ref={dotRef} className="glow-cursor-dot" />
    </div>
  );
}
