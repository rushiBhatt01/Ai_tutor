const particles = Array.from({ length: 22 }, (_, index) => ({
  id: index,
  left: `${(index * 11.5) % 100}%`,
  top: `${(index * 17.25) % 100}%`,
  size: `${4 + (index % 5) * 3}px`,
  delay: `${(index % 7) * -1.6}s`,
  duration: `${18 + (index % 6) * 4}s`,
}));

export default function FloatingParticles() {
  return (
    <div aria-hidden="true" className="particle-field">
      {particles.map((particle) => (
        <span
          key={particle.id}
          style={{
            left: particle.left,
            top: particle.top,
            width: particle.size,
            height: particle.size,
            "--delay": particle.delay,
            "--duration": particle.duration,
          }}
        />
      ))}
    </div>
  );
}
