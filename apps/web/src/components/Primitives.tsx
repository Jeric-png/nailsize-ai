import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

export function Button({
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`button ${className}`.trim()} {...props} />;
}

export function Card({
  children,
  className = "",
}: PropsWithChildren<{ className?: string }>) {
  return <section className={`card ${className}`.trim()}>{children}</section>;
}

export function Eyebrow({ children }: PropsWithChildren) {
  return <p className="eyebrow">{children}</p>;
}

export function StatusMessage({
  children,
  tone = "neutral",
}: PropsWithChildren<{ tone?: "neutral" | "error" | "success" }>) {
  return (
    <div
      className={`status status--${tone}`}
      role={tone === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}

export function ProgressStepper({ current }: { current: number }) {
  return (
    <ol className="stepper" aria-label={`Capture ${current} of 4`}>
      {[1, 2, 3, 4].map((step) => (
        <li
          key={step}
          className={
            step <= current
              ? "stepper__step stepper__step--active"
              : "stepper__step"
          }
        >
          <span>{step}</span>
        </li>
      ))}
    </ol>
  );
}
