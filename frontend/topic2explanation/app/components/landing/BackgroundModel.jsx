"use client";

import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";

const MODEL_URL = "/models/benjamin.glb";

/* ── Scroll-driven rotating model ────────────────────────── */
function RotatingModel() {
  const pivot = useRef(null);
  const gltf = useLoader(GLTFLoader, MODEL_URL);
  const scene = useMemo(() => clone(gltf.scene), [gltf.scene]);
  const mixer = useRef(null);

  /* Normalize scale & center the model */
  const transform = useMemo(() => {
    scene.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(scene);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const targetHeight = 2.0;
    const scale = targetHeight / Math.max(size.y, 0.01);

    return {
      scale,
      position: [
        -center.x * scale,
        -center.y * scale,
        -center.z * scale,
      ],
    };
  }, [scene]);

  /* Material tweaks — ghostly translucent look */
  useEffect(() => {
    scene.traverse((node) => {
      if (!node.isMesh) return;

      const mats = Array.isArray(node.material)
        ? node.material
        : [node.material];

      mats.forEach((mat) => {
        if (!mat) return;
        mat.transparent = false;
        mat.depthWrite = true;
        mat.side = THREE.FrontSide;
        if ("roughness" in mat) mat.roughness = 0.6;
        if ("metalness" in mat) mat.metalness = 0.1;
        if ("emissive" in mat) {
          mat.emissive = new THREE.Color("#4a3f8a");
          mat.emissiveIntensity = 0.15;
        }
        mat.needsUpdate = true;
      });
    });

    /* Play idle animation if available */
    if (!gltf.animations?.length) return undefined;

    mixer.current = new THREE.AnimationMixer(scene);
    const clip =
      gltf.animations.find((a) =>
        /idle|breath|look|pose|standing|neutral|rest/i.test(a.name)
      ) || gltf.animations[0];
    const action = mixer.current.clipAction(clip);
    action.setLoop(THREE.LoopRepeat, Infinity);
    action.fadeIn(0.3);
    action.play();

    return () => {
      action.fadeOut(0.2);
      action.stop();
      mixer.current?.stopAllAction();
      mixer.current?.uncacheRoot(scene);
      mixer.current = null;
    };
  }, [gltf.animations, scene]);

  /* Frame loop: animate mixer + read scroll progress from DOM */
  useFrame((state, delta) => {
    if (mixer.current) mixer.current.update(delta);
    if (!pivot.current) return;

    /* Read the CSS custom property set by GSAP ScrollTrigger */
    const el = document.querySelector("[data-bg-model]");
    const raw = el
      ? getComputedStyle(el).getPropertyValue("--bg-model-scroll")
      : "0";
    const scrollProgress = parseFloat(raw) || 0;

    /* Smoothly lerp towards target rotation */
    const targetY = scrollProgress * Math.PI * 2;
    pivot.current.rotation.y = THREE.MathUtils.lerp(
      pivot.current.rotation.y,
      targetY,
      0.08
    );

    /* Gentle bob */
    pivot.current.position.y =
      Math.sin(state.clock.elapsedTime * 0.8) * 0.04;
  });

  return (
    <group ref={pivot}>
      <group position={transform.position} scale={transform.scale}>
        <primitive object={scene} />
      </group>
    </group>
  );
}

/* ── Fixed fullscreen background canvas ──────────────────── */
export default function BackgroundModel() {
  return (
    <div className="bg-model-container" data-bg-model>
      <Canvas
        camera={{ position: [0, 0.4, 4.8], fov: 30 }}
        dpr={[1, 1.3]}
        gl={{ alpha: true, antialias: true }}
      >
        {/* Subtle lighting — enough to see form, not overpower */}
        <ambientLight intensity={0.6} />
        <hemisphereLight
          skyColor="#b0a7ff"
          groundColor="#16162b"
          intensity={0.5}
        />
        <directionalLight
          position={[2, 4, 3]}
          intensity={1.2}
          color="#c2b6ff"
        />
        <pointLight position={[-1, 2, 2]} intensity={6} color="#8058ff" />
        <Suspense fallback={null}>
          <RotatingModel />
        </Suspense>
      </Canvas>
    </div>
  );
}
