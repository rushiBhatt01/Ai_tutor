"use client";

import { useEffect } from "react";
import Lenis from "lenis";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

export default function useLandingMotion() {
  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    let lenis = null;
    let removeTicker = null;

    if (!prefersReducedMotion) {
      lenis = new Lenis({
        duration: 1.1,
        smoothWheel: true,
        syncTouch: false,
      });

      lenis.on("scroll", ScrollTrigger.update);

      const onTick = (time) => {
        lenis.raf(time * 1000);
      };

      gsap.ticker.add(onTick);
      gsap.ticker.lagSmoothing(0);
      removeTicker = () => gsap.ticker.remove(onTick);
    }

    const ctx = gsap.context(() => {
      gsap.fromTo(
        "[data-hero-copy]",
        { autoAlpha: 0, y: 42 },
        { autoAlpha: 1, y: 0, duration: 1, ease: "power3.out" }
      );

      gsap.fromTo(
        "[data-hero-orb]",
        { autoAlpha: 0, scale: 0.9, y: 30 },
        {
          autoAlpha: 1,
          scale: 1,
          y: 0,
          delay: 0.12,
          duration: 1.1,
          ease: "power3.out",
        }
      );

      gsap.to("[data-float]", {
        y: -16,
        duration: 4.2,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
      });

      gsap.utils.toArray("[data-float-chip]").forEach((element, index) => {
        const chipIndex = Number(element.dataset.chipIndex || index);
        const direction = chipIndex % 2 === 0 ? -1 : 1;

        gsap.to(element, {
          y: 12 * direction,
          x: 6 * -direction,
          duration: 3.4 + chipIndex * 0.35,
          repeat: -1,
          yoyo: true,
          ease: "sine.inOut",
        });
      });

      gsap.utils.toArray("[data-reveal]").forEach((element, index) => {
        gsap.fromTo(
          element,
          { autoAlpha: 0, y: 54 },
          {
            autoAlpha: 1,
            y: 0,
            duration: 0.9,
            delay: index % 3 === 0 ? 0 : 0.06,
            ease: "power3.out",
            scrollTrigger: {
              trigger: element,
              start: "top 84%",
              once: true,
            },
          }
        );
      });

      /* ── Staggered word reveal in section headings ───── */
      gsap.utils.toArray("[data-stagger-heading]").forEach((heading) => {
        const words = heading.querySelectorAll("[data-stagger-word]");
        if (!words.length) return;

        gsap.fromTo(
          words,
          { autoAlpha: 0, y: 24 },
          {
            autoAlpha: 1,
            y: 0,
            duration: 0.6,
            stagger: 0.08,
            ease: "power3.out",
            scrollTrigger: {
              trigger: heading,
              start: "top 85%",
              once: true,
            },
          }
        );
      });

      /* ── Slot-machine counter digits ───── */
      gsap.utils.toArray("[data-slot-counter]").forEach((counter) => {
        const digits = counter.querySelectorAll("[data-slot-digit]");
        ScrollTrigger.create({
          trigger: counter,
          start: "top 88%",
          once: true,
          onEnter: () => {
            digits.forEach((digit) => {
              digit.classList.add("active");
            });
          },
        });
      });

      gsap.utils.toArray("[data-parallax]").forEach((element) => {
        gsap.to(element, {
          yPercent: -10,
          ease: "none",
          scrollTrigger: {
            trigger: element,
            start: "top bottom",
            end: "bottom top",
            scrub: true,
          },
        });
      });

      gsap.utils.toArray("[data-visual-panel]").forEach((element) => {
        gsap.fromTo(
          element,
          { scale: 0.94, autoAlpha: 0.45 },
          {
            scale: 1,
            autoAlpha: 1,
            ease: "none",
            scrollTrigger: {
              trigger: element,
              start: "top 80%",
              end: "top 25%",
              scrub: true,
            },
          }
        );
      });

      /* data-count counters removed — replaced by slot-machine above */

      /* ── Scroll-driven 3D background model rotation ───── */
      const bgModelEl = document.querySelector("[data-bg-model]");
      if (bgModelEl) {
        gsap.to(bgModelEl, {
          "--bg-model-scroll": 1,
          ease: "none",
          scrollTrigger: {
            trigger: document.body,
            start: "top top",
            end: "bottom bottom",
            scrub: 1.5,
          },
        });
      }
    });

    ScrollTrigger.refresh();

    return () => {
      ctx.revert();
      if (removeTicker) {
        removeTicker();
      }
      if (lenis) {
        lenis.destroy();
      }
    };
  }, []);
}
