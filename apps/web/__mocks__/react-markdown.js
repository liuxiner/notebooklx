// Mock for react-markdown (ESM) for Jest.
// Renders text content through the custom component overrides (p, li, strong, etc.)
// so that citation processing via processChildren still works in tests.
const React = require("react");

function ReactMarkdown({ children, components }) {
  const text = typeof children === "string" ? children : String(children);

  // Use the custom "p" component if provided (MarkdownWithCitations always provides one)
  const P = components?.p;
  if (P) {
    return React.createElement(P, null, text);
  }

  return React.createElement("div", null, text);
}

module.exports = ReactMarkdown;
