"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useRef } from "react";

const wireframeGeometry = new THREE.IcosahedronGeometry(1.45, 1);

function ParticleHalo() {
  const points = useRef(null);
  const positions = useRef(null);

  if (!positions.current) {
    const values = [];

    for (let index = 0; index < 280; index += 1) {
      const radius = 2 + Math.random() * 1.15;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      values.push(
        radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.sin(phi) * Math.sin(theta),
        radius * Math.cos(phi)
      );
    }

    positions.current = new Float32Array(values);
  }

  useFrame((state, delta) => {
    if (!points.current) {
      return;
    }

    points.current.rotation.y += delta * 0.04;
    points.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.24) * 0.2;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          array={positions.current}
          count={positions.current.length / 3}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        color="#84f6ff"
        size={0.026}
        sizeAttenuation
        transparent
        opacity={0.75}
      />
    </points>
  );
}

function NeuralOrb({ interactive }) {
  const group = useRef(null);
  const inner = useRef(null);
  const shell = useRef(null);

  useFrame((state, delta) => {
    if (!group.current || !inner.current || !shell.current) {
      return;
    }

    const elapsed = state.clock.elapsedTime;
    const targetX = interactive ? state.pointer.y * 0.35 : 0.16;
    const targetY = interactive ? state.pointer.x * 0.55 : 0.3;

    group.current.rotation.x = THREE.MathUtils.lerp(
      group.current.rotation.x,
      targetX,
      0.05
    );
    group.current.rotation.y = THREE.MathUtils.lerp(
      group.current.rotation.y,
      targetY + elapsed * 0.18,
      0.04
    );
    group.current.position.y = Math.sin(elapsed * 1.1) * 0.12;

    inner.current.rotation.y += delta * 0.22;
    shell.current.rotation.x -= delta * 0.12;
    shell.current.rotation.z += delta * 0.16;
  });

  return (
    <group ref={group}>
      <mesh ref={inner}>
        <icosahedronGeometry args={[1.05, 18]} />
        <meshPhysicalMaterial
          color="#79e9ff"
          roughness={0.18}
          metalness={0.72}
          transmission={0.2}
          transparent
          opacity={0.92}
          emissive="#00c2ff"
          emissiveIntensity={0.45}
        />
      </mesh>

      <lineSegments ref={shell}>
        <edgesGeometry args={[wireframeGeometry]} />
        <lineBasicMaterial color="#e6fcff" transparent opacity={0.42} />
      </lineSegments>

      <mesh rotation={[Math.PI / 2, 0.12, 0.2]}>
        <torusGeometry args={[1.82, 0.03, 16, 140]} />
        <meshBasicMaterial color="#6ef2ff" transparent opacity={0.65} />
      </mesh>

      <mesh rotation={[1.05, 0.45, 0]}>
        <torusGeometry args={[2.18, 0.02, 16, 140]} />
        <meshBasicMaterial color="#8058ff" transparent opacity={0.45} />
      </mesh>
    </group>
  );
}

export default function OrbCanvas({ interactive = false }) {
  return (
    <Canvas
      camera={{ position: [0, 0, 4.8], fov: 42 }}
      dpr={[1, 1.6]}
      gl={{ alpha: true, antialias: true }}
    >
      <ambientLight intensity={0.7} />
      <directionalLight color="#f7fbff" intensity={1.2} position={[3, 3, 4]} />
      <pointLight color="#7a5cff" intensity={14} position={[-2.4, 1.2, 1.8]} />
      <pointLight color="#6ef2ff" intensity={18} position={[2.6, -0.5, 2.5]} />
      <NeuralOrb interactive={interactive} />
      <ParticleHalo />
    </Canvas>
  );
}
