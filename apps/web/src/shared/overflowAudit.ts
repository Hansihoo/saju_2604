export type HorizontalOverflowIssue = {
  selector: string;
  scrollWidth: number;
  clientWidth: number;
};

function isVisible(element: HTMLElement) {
  return element.getClientRects().length > 0 && window.getComputedStyle(element).display !== "none";
}

function hasIntentionalScrollContainer(element: HTMLElement, root: HTMLElement) {
  let current: HTMLElement | null = element;

  while (current) {
    const overflowX = window.getComputedStyle(current).overflowX;

    if (overflowX === "auto" || overflowX === "scroll") {
      return true;
    }

    if (current === root) {
      break;
    }

    current = current.parentElement;
  }

  return false;
}

function getElementSelector(element: HTMLElement) {
  const className = typeof element.className === "string"
    ? element.className.trim().split(/\s+/).filter(Boolean).slice(0, 2).join(".")
    : "";

  return `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ""}${className ? `.${className}` : ""}`;
}

export function collectHorizontalOverflow(root: HTMLElement): HorizontalOverflowIssue[] {
  const candidates = [root, ...Array.from(root.querySelectorAll<HTMLElement>("*"))];

  return candidates
    .filter((element) => {
      if (!isVisible(element) || element.hasAttribute("data-overflow-ignore")) {
        return false;
      }

      if (hasIntentionalScrollContainer(element, root)) {
        return false;
      }

      return element.scrollWidth > element.clientWidth + 1;
    })
    .slice(0, 24)
    .map((element) => ({
      selector: getElementSelector(element),
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
    }));
}

export function installHorizontalOverflowAudit(root: HTMLElement) {
  if (typeof window === "undefined" || typeof window.requestAnimationFrame !== "function") {
    return () => undefined;
  }

  let frameId: number | null = null;
  let previousSignature: string | null = null;

  const run = () => {
    frameId = null;
    const issues = collectHorizontalOverflow(root);
    const signature = issues
      .map((issue) => `${issue.selector}:${issue.scrollWidth}/${issue.clientWidth}`)
      .join("|");

    if (signature === previousSignature) {
      return;
    }

    previousSignature = signature;
    root.dataset.overflowAuditStatus = issues.length ? "fail" : "pass";
    root.dataset.overflowAuditCount = String(issues.length);

    if (issues.length && import.meta.env.DEV) {
      console.warn("[overflow-audit] horizontal overflow detected", issues);
    }
  };

  const schedule = () => {
    if (frameId !== null) {
      return;
    }

    frameId = window.requestAnimationFrame(run);
  };

  const resizeObserver = typeof ResizeObserver !== "undefined"
    ? new ResizeObserver(schedule)
    : null;
  const mutationObserver = typeof MutationObserver !== "undefined"
    ? new MutationObserver(schedule)
    : null;

  resizeObserver?.observe(root);
  mutationObserver?.observe(root, {
    attributes: true,
    childList: true,
    characterData: true,
    subtree: true,
  });
  window.addEventListener("resize", schedule);
  run();

  return () => {
    if (frameId !== null) {
      window.cancelAnimationFrame(frameId);
    }

    resizeObserver?.disconnect();
    mutationObserver?.disconnect();
    window.removeEventListener("resize", schedule);
    delete root.dataset.overflowAuditStatus;
    delete root.dataset.overflowAuditCount;
  };
}

export function installResultOverflowAuditObserver(container: HTMLElement) {
  let observedRoot: HTMLElement | null = null;
  let teardownAudit: (() => void) | null = null;

  const attach = () => {
    const nextRoot = container.querySelector<HTMLElement>("[data-overflow-audit-root]");

    if (nextRoot === observedRoot) {
      return;
    }

    teardownAudit?.();
    teardownAudit = null;
    observedRoot = nextRoot;

    if (!nextRoot) {
      if (window.__sajuOverflowAudit) {
        delete window.__sajuOverflowAudit;
      }
      return;
    }

    const audit = () => collectHorizontalOverflow(nextRoot);
    nextRoot.dataset.overflowAuditStatus = "pending";
    nextRoot.dataset.overflowAuditCount = "";
    window.__sajuOverflowAudit = audit;
    teardownAudit = installHorizontalOverflowAudit(nextRoot);
  };

  const mutationObserver = typeof MutationObserver !== "undefined"
    ? new MutationObserver(attach)
    : null;

  mutationObserver?.observe(container, {
    childList: true,
    subtree: true,
  });
  attach();

  return () => {
    mutationObserver?.disconnect();
    teardownAudit?.();
    teardownAudit = null;
    observedRoot = null;

    if (window.__sajuOverflowAudit) {
      delete window.__sajuOverflowAudit;
    }
  };
}

declare global {
  interface Window {
    __sajuOverflowAudit?: () => HorizontalOverflowIssue[];
  }
}
