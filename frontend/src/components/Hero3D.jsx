import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { ContactShadows, RoundedBox } from "@react-three/drei";

const CLAY = { roughness: 0.55, metalness: 0 };
const Clay = ({ color }) => <meshStandardMaterial color={color} {...CLAY} />;

// ---- marks drawn with chunky clay strokes ----
const Check = () => (
  <group>
    <RoundedBox args={[0.15, 0.36, 0.12]} radius={0.06} position={[-0.17, -0.07, 0]} rotation={[0, 0, 0.8]}><Clay color="#FFFFFF" /></RoundedBox>
    <RoundedBox args={[0.15, 0.66, 0.12]} radius={0.06} position={[0.11, 0.02, 0]} rotation={[0, 0, -0.7]}><Clay color="#FFFFFF" /></RoundedBox>
  </group>
);
const Cross = () => (
  <group>
    <RoundedBox args={[0.16, 0.62, 0.12]} radius={0.06} rotation={[0, 0, Math.PI / 4]}><Clay color="#FFFFFF" /></RoundedBox>
    <RoundedBox args={[0.16, 0.62, 0.12]} radius={0.06} rotation={[0, 0, -Math.PI / 4]}><Clay color="#FFFFFF" /></RoundedBox>
  </group>
);
const Question = () => (
  <group>
    <mesh position={[0, 0.12, 0]} rotation={[0, 0, -0.4]}><torusGeometry args={[0.2, 0.07, 14, 28, Math.PI * 1.5]} /><Clay color="#FFFFFF" /></mesh>
    <mesh position={[0.02, -0.28, 0]}><sphereGeometry args={[0.07, 16, 16]} /><Clay color="#FFFFFF" /></mesh>
  </group>
);

// A chunky badge that bounces; bounces higher and faster while a PDF is being analyzed.
function Badge({ position, phase, active, children, size = 0.95, color, round }) {
  const g = useRef();
  useFrame((s) => {
    const t = s.clock.elapsedTime * (active ? 1.2 : 0.6) + phase;
    g.current.position.y = position[1] + Math.sin(t) * (active ? 0.09 : 0.05);
    g.current.rotation.z = Math.sin(t * 0.5) * 0.03;
  });
  return (
    <group ref={g} position={position}>
      {round ? (
        <mesh><sphereGeometry args={[size * 0.55, 40, 40]} /><Clay color={color} /></mesh>
      ) : (
        <RoundedBox args={[size, size, size]} radius={0.12} smoothness={6}><Clay color={color} /></RoundedBox>
      )}
      <group position={[0, 0, size * (round ? 0.54 : 0.5) + 0.01]}>{children}</group>
    </group>
  );
}

function Paper({ active }) {
  const bar = useRef(), phase = useRef(0);
  useFrame((_, dt) => {
    phase.current += dt * (active ? 1.8 : 0.6);
    bar.current.position.y = Math.sin(phase.current) * 1.25;
  });
  const rows = [[1.2, "#CBD5E1"], [1.5, "#94A3B8"], [1.0, "#CBD5E1"], [1.6, "#94A3B8"], [1.3, "#CBD5E1"], [0.9, "#94A3B8"]];
  return (
    <group>
      <RoundedBox args={[2.7, 3.5, 0.4]} radius={0.2} smoothness={6}><Clay color="#FFFFFF" /></RoundedBox>
      <RoundedBox args={[2.7, 3.5, 0.4]} radius={0.2} smoothness={6} position={[0.18, -0.16, -0.36]} rotation={[0, 0, -0.05]}><Clay color="#DBEAFE" /></RoundedBox>
      <RoundedBox args={[1.5, 0.2, 0.14]} radius={0.09} position={[-0.4, 1.3, 0.26]}><Clay color="#1D4ED8" /></RoundedBox>
      {rows.map(([w, c], i) => (
        <RoundedBox key={i} args={[w, 0.15, 0.12]} radius={0.07} position={[-1.05 + w / 2 + 0.2, 0.7 - i * 0.42, 0.25]}><Clay color={c} /></RoundedBox>
      ))}
      <group ref={bar} position={[0, 0, 0.3]}>
        <RoundedBox args={[3.0, 0.2, 0.3]} radius={0.1} smoothness={5}><Clay color="#1D4ED8" /></RoundedBox>
      </group>
    </group>
  );
}

function Scene({ active }) {
  const g = useRef();
  useFrame((s) => {
    g.current.rotation.y += (-0.35 + s.pointer.x * 0.3 - g.current.rotation.y) * 0.05;
    g.current.rotation.x += (0.12 - s.pointer.y * 0.1 - g.current.rotation.x) * 0.05;
  });
  return (
    <>
      <ambientLight intensity={1.15} />
      <directionalLight position={[3, 5, 6]} intensity={1.6} color="#FFFFFF" />
      <directionalLight position={[-4, -2, 3]} intensity={0.5} color="#94A3B8" />
      <group ref={g}>
        <Paper active={active} />
        <Badge position={[-2.35, 1.1, 0.5]} phase={0} active={active} color="#1D4ED8"><Check /></Badge>
        <Badge position={[2.35, 0.7, 0.7]} phase={1.7} active={active} color="#DC2626" round size={1.1}><Cross /></Badge>
        <Badge position={[2.05, -1.5, 0.9]} phase={3.1} active={active} color="#64748B" size={0.9}><Question /></Badge>
        <mesh position={[-2.1, -1.5, 0.4]}><sphereGeometry args={[0.28, 24, 24]} /><Clay color="#DC2626" /></mesh>
        <mesh position={[-1.6, 2.0, 0.3]}><sphereGeometry args={[0.17, 24, 24]} /><Clay color="#1D4ED8" /></mesh>
      </group>
      <ContactShadows position={[0, -2.35, 0]} opacity={0.16} scale={9} blur={2.6} far={3} resolution={256} color="#1E3A8A" />
    </>
  );
}

export default function Hero3D({ scanning }) {
  return (
    <Canvas dpr={[1, 1.75]} camera={{ position: [0, 0, 9], fov: 38 }} gl={{ alpha: true, antialias: true }}>
      <Scene active={scanning} />
    </Canvas>
  );
}
