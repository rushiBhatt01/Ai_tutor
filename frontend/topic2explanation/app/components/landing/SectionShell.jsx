"use client";

function StaggerTitle({ text }) {
  const words = text.split(" ");
  return (
    <>
      {words.map((word, i) => (
        <span
          key={i}
          className="stagger-word"
          data-stagger-word
          style={{ "--word-i": i }}
        >
          {word}{" "}
        </span>
      ))}
    </>
  );
}

export default function SectionShell({
  id,
  eyebrow,
  title,
  description,
  align = "left",
  className = "",
  children,
}) {
  const isCentered = align === "center";

  return (
    <section id={id} className={`relative py-24 sm:py-28 ${className}`}>
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div
          className={
            isCentered
              ? "mx-auto max-w-3xl text-center"
              : "max-w-3xl text-left"
          }
          data-reveal
        >
          <span className="eyebrow">{eyebrow}</span>
          <h2
            className="display-font mt-6 text-3xl font-semibold leading-tight text-white sm:text-4xl lg:text-5xl"
            data-stagger-heading
          >
            <StaggerTitle text={title} />
          </h2>
          <p className="section-copy mt-5">{description}</p>
        </div>
        <div className="mt-14">{children}</div>
      </div>
    </section>
  );
}
