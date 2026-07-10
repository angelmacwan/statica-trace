/**
 * Vitest setup file — imported before every test file via vitest.config.ts
 * setupFiles option.
 *
 * Extends Vitest's expect with @testing-library/jest-dom matchers so we can
 * write assertions like:
 *   expect(element).toBeInTheDocument()
 *   expect(button).toBeDisabled()
 */
import "@testing-library/jest-dom";
