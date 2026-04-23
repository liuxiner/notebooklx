// Mock for remark-gfm (ESM) — returns a no-op plugin.
module.exports = function remarkGfm() {
  return function () {};
};
