/**
 * Button.tsx — a trivial reusable button component used in the smoke test.
 *
 * This is the minimal component required by backlog item 0.2.1:
 * "A trivial smoke test exists and passes (e.g. renders a <Button> component
 *  and asserts it's in the DOM)."
 */
import type { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
}

export function Button({ children, ...props }: ButtonProps) {
  return <button {...props}>{children}</button>;
}
