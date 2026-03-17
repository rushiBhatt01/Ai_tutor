"use client";

import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";

const MODEL_URL = "/models/benjamin.glb";

function CameraRig({ compact }) {
  const { camera } = useThree();

  useEffect(() => {
    camera.position.set(0, compact ? 1.52 : 1.62, compact ? 2.02 : 2.2);
    camera.lookAt(0, compact ? 1.2 : 1.28, 0);
  }, [camera, compact]);

  useFrame((state) => {
    const targetX = state.pointer.x * 0.06;
    const targetY = (compact ? 1.2 : 1.28) + state.pointer.y * 0.05;

    camera.position.x = THREE.MathUtils.lerp(
      camera.position.x,
      state.pointer.x * 0.05,
      0.03
    );
    camera.lookAt(targetX, targetY, 0);
  });

  return null;
}

function ModelRig({ compact }) {
  const pivot = useRef(null);
  const pointsRef = useRef(null);
  const yawRef = useRef(0);
  const gltf = useLoader(GLTFLoader, MODEL_URL);
  const scene = useMemo(() => clone(gltf.scene), [gltf.scene]);
  const mixer = useRef(null);

  const normalizedTransform = useMemo(() => {
    scene.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(scene);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const targetHeight = compact ? 2.25 : 2.45;
    const scale = targetHeight / Math.max(size.y, 0.01);
    const framedTopY = compact ? 1.62 : 1.72;

    return {
      scale,
      position: [
        -center.x * scale,
        framedTopY - box.max.y * scale,
        -center.z * scale,
      ],
    };
  }, [compact, scene]);
  const particleGeometry = useMemo(() => {
    scene.updateMatrixWorld(true);

    const allBounds = new THREE.Box3().setFromObject(scene);
    const boundsSize = allBounds.getSize(new THREE.Vector3());
    const yCutoff = allBounds.min.y + boundsSize.y * 0.43;
    const positions = [];
    const tmp = new THREE.Vector3();

    scene.traverse((node) => {
      if (!node.isMesh || !node.geometry?.attributes?.position) {
        return;
      }

      const attr = node.geometry.attributes.position;
      const step = Math.max(1, Math.floor(attr.count / 2200));

      for (let index = 0; index < attr.count; index += step) {
        tmp.fromBufferAttribute(attr, index);
        tmp.applyMatrix4(node.matrixWorld);

        if (tmp.y < yCutoff) {
          continue;
        }

        positions.push(
          tmp.x + (Math.random() - 0.5) * 0.008,
          tmp.y + (Math.random() - 0.5) * 0.008,
          tmp.z + (Math.random() - 0.5) * 0.008
        );
      }
    });

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(positions, 3)
    );
    return geometry;
  }, [scene]);

  useEffect(() => {
    scene.traverse((node) => {
      if (node.isMesh) {
        node.castShadow = true;
        node.receiveShadow = true;

        const materials = Array.isArray(node.material)
          ? node.material
          : [node.material];

        materials.forEach((material) => {
          if (!material) {
            return;
          }

          if ("emissive" in material) {
            material.emissiveIntensity = Math.max(
              material.emissiveIntensity ?? 0,
              0.03
            );
          }

          if ("roughness" in material) {
            material.roughness = THREE.MathUtils.clamp(
              material.roughness ?? 0.75,
              0.35,
              0.95
            );
          }

          if ("metalness" in material) {
            material.metalness = Math.min(material.metalness ?? 0.2, 0.15);
          }
          material.needsUpdate = true;
        });
      }
    });

    if (!gltf.animations?.length) {
      return undefined;
    }

    mixer.current = new THREE.AnimationMixer(scene);
    const clip =
      gltf.animations.find((animation) =>
        /idle|breath|look|pose|standing|neutral|rest/i.test(animation.name)
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

  useFrame((state, delta) => {
    if (mixer.current) {
      mixer.current.update(delta);
    }

    if (!pivot.current) {
      return;
    }

    yawRef.current = (yawRef.current + delta * 0.42) % (Math.PI * 2);
    const targetY = yawRef.current + state.pointer.x * 0.22;
    const targetX = state.pointer.y * 0.035;

    pivot.current.rotation.y = THREE.MathUtils.lerp(
      pivot.current.rotation.y,
      targetY,
      0.08
    );
    pivot.current.rotation.x = THREE.MathUtils.lerp(
      pivot.current.rotation.x,
      targetX,
      0.05
    );
    pivot.current.position.y = Math.sin(state.clock.elapsedTime * 1.18) * 0.025;

    if (pointsRef.current) {
      pointsRef.current.rotation.y += delta * 0.045;
      pointsRef.current.material.opacity =
        0.5 + Math.sin(state.clock.elapsedTime * 1.2) * 0.08;
    }
  });

  return (
    <group ref={pivot}>
      <group
        position={normalizedTransform.position}
        scale={normalizedTransform.scale}
      >
        <primitive object={scene} />
        <points ref={pointsRef} geometry={particleGeometry}>
          <pointsMaterial
            color="#b0a7ff"
            size={compact ? 0.011 : 0.013}
            sizeAttenuation
            transparent
            opacity={0.34}
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </points>
      </group>
    </group>
  );
}

function StageAccents() {
  return (
    <group>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, -2.42, 0]}>
        <ringGeometry args={[0.95, 1.28, 96]} />
        <meshBasicMaterial
          color="#6ef2ff"
          transparent
          opacity={0.22}
          side={THREE.DoubleSide}
        />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, -2.4, 0]}>
        <ringGeometry args={[1.42, 1.5, 96]} />
        <meshBasicMaterial
          color="#8058ff"
          transparent
          opacity={0.16}
          side={THREE.DoubleSide}
        />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.95, -0.65]}>
        <circleGeometry args={[2.4, 64]} />
        <meshBasicMaterial color="#221b3d" transparent opacity={0.14} />
      </mesh>
    </group>
  );
}

export default function HumanoidModelCanvas({ compact = false }) {
  return (
    <div className="model-canvas-shell">
      <Canvas
        camera={{ position: [0, 1.62, 2.2], fov: 32 }}
        dpr={[1, 1.5]}
        gl={{ alpha: false, antialias: true }}
      >
        <color attach="background" args={["#060613"]} />
        <fog attach="fog" args={["#060613", 4.8, 9.4]} />
        <CameraRig compact={compact} />
        <hemisphereLight
          skyColor="#e7e4ff"
          groundColor="#16162b"
          intensity={1.05}
        />
        <ambientLight intensity={1.15} />
        <directionalLight
          position={[2.1, 4.6, 3.8]}
          intensity={2.4}
          color="#f5f1ff"
        />
        <directionalLight
          position={[-2.8, 2.2, 3.1]}
          intensity={1.25}
          color="#8f83ff"
        />
        <pointLight position={[0.25, 2.1, 2.3]} intensity={14} color="#c2b6ff" />
        <pointLight position={[-0.8, 1.15, 2.0]} intensity={8.5} color="#8c7fff" />
        <pointLight position={[0, -0.9, 2.2]} intensity={4.6} color="#34304f" />
        <Suspense fallback={null}>
          <StageAccents />
          <ModelRig compact={compact} />
        </Suspense>
      </Canvas>
      <div className="model-vignette" />
    </div>
  );
}
