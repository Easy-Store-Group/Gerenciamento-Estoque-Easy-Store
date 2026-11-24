(() => {
  const CONFIG = Object.freeze({
    showDelay: 180,
    minimumVisible: 450,
    messageInterval: 2800,
    maxDuration: 30000,
  });

  const MESSAGES = {
    page: [
      "Estamos preparando tudo para você...",
      "Só mais um instante...",
      "Organizando as informações...",
    ],
    data: [
      "Organizando suas informações...",
      "Só mais um instante...",
      "Estamos sincronizando os dados...",
    ],
    sync: [
      "Estamos sincronizando os dados...",
      "Organizando as informações...",
      "Quase tudo pronto...",
    ],
    init: [
      "Preparando seu ambiente...",
      "Carregando sua experiência...",
      "Estamos preparando tudo para você...",
    ],
  };

  let overlay;
  let messageElement;
  let showTimer = null;
  let hideTimer = null;
  let safetyTimer = null;
  let fadeTimer = null;
  let messageTimer = null;
  let visibleSince = 0;
  let isVisible = false;
  let context = "page";
  let messageIndex = 0;
  let counter = 0;
  const operations = new Map();

  function ensureMarkup() {
    if (overlay) return;

    overlay = document.createElement("div");
    overlay.className = "easystore-loading";
    overlay.setAttribute("role", "status");
    overlay.setAttribute("aria-live", "polite");
    overlay.setAttribute("aria-busy", "false");
    overlay.setAttribute("aria-hidden", "true");
    overlay.innerHTML = `
      <div class="easystore-loading__content">
        <span class="easystore-loading__spinner" aria-hidden="true"></span>
        <p class="easystore-loading__message"></p>
      </div>`;

    messageElement = overlay.querySelector(".easystore-loading__message");
    document.body.appendChild(overlay);
  }

  function getMessages(requestedContext) {
    return MESSAGES[requestedContext] || MESSAGES.page;
  }

  function setMessage(nextMessage) {
    if (!messageElement || messageElement.textContent === nextMessage) return;
    messageElement.classList.add("is-changing");
    if (fadeTimer) window.clearTimeout(fadeTimer);
    fadeTimer = window.setTimeout(() => {
      fadeTimer = null;
      messageElement.textContent = nextMessage;
      messageElement.classList.remove("is-changing");
    }, 220);
  }

  function startMessageRotation() {
    stopMessageRotation();
    const messages = getMessages(context);
    messageIndex = 0;
    messageElement.textContent = messages[0];

    messageTimer = window.setInterval(() => {
      messageIndex = (messageIndex + 1) % messages.length;
      setMessage(messages[messageIndex]);
    }, CONFIG.messageInterval);
  }

  function stopMessageRotation() {
    if (messageTimer) {
      window.clearInterval(messageTimer);
      messageTimer = null;
    }
  }

  function show(options = {}) {
    ensureMarkup();

    context = options.context && MESSAGES[options.context] ? options.context : "page";
    overlay.classList.toggle("is-passive", options.blocking === false);

    if (isVisible) {
      return;
    }

    if (showTimer) window.clearTimeout(showTimer);
    showTimer = window.setTimeout(() => {
      showTimer = null;
      isVisible = true;
      visibleSince = Date.now();
      overlay.classList.add("is-visible");
      overlay.setAttribute("aria-hidden", "false");
      overlay.setAttribute("aria-busy", "true");
      document.body.setAttribute("aria-busy", "true");
      if (overlay.classList.contains("is-passive") === false) {
        document.body.classList.add("easystore-loading-active");
      }
      startMessageRotation();

      safetyTimer = window.setTimeout(() => {
        forceEnd();
      }, CONFIG.maxDuration);
    }, CONFIG.showDelay);
  }

  function hide() {
    if (hideTimer) {
      window.clearTimeout(hideTimer);
      hideTimer = null;
    }

    if (showTimer) {
      window.clearTimeout(showTimer);
      showTimer = null;
      isVisible = false;
      return;
    }

    if (!isVisible) return;

    const remaining = Math.max(0, CONFIG.minimumVisible - (Date.now() - visibleSince));
    hideTimer = window.setTimeout(() => {
      hideTimer = null;
      isVisible = false;
      stopMessageRotation();
      if (safetyTimer) window.clearTimeout(safetyTimer);
      safetyTimer = null;
      overlay.classList.remove("is-visible");
      overlay.setAttribute("aria-hidden", "true");
      overlay.setAttribute("aria-busy", "false");
      document.body.removeAttribute("aria-busy");
      document.body.classList.remove("easystore-loading-active");
    }, remaining);
  }

  function forceEnd() {
    if (showTimer) {
      window.clearTimeout(showTimer);
      showTimer = null;
    }
    if (hideTimer) {
      window.clearTimeout(hideTimer);
      hideTimer = null;
    }
    if (safetyTimer) {
      window.clearTimeout(safetyTimer);
      safetyTimer = null;
    }
    operations.clear();
    counter = 0;
    isVisible = false;
    stopMessageRotation();

    if (overlay) {
      overlay.classList.remove("is-visible");
      overlay.setAttribute("aria-hidden", "true");
      overlay.setAttribute("aria-busy", "false");
    }
    document.body.removeAttribute("aria-busy");
  }

  function refresh() {
    if (operations.size === 0) {
      hide();
      return;
    }

    const first = operations.values().next().value;
    show({ context: first.context, blocking: first.blocking });
  }

  function begin(options = {}) {
    ensureMarkup();
    const id = options.id || `loading-${++counter}`;
    operations.set(id, {
      context: options.context || "page",
      blocking: options.blocking !== false,
    });
    refresh();
    return id;
  }

  function end(id) {
    if (id) operations.delete(id);
    else operations.clear();
    refresh();
  }

  async function track(promiseOrFunction, options = {}) {
    const id = begin(options);
    try {
      const value = typeof promiseOrFunction === "function"
        ? await promiseOrFunction()
        : await promiseOrFunction;
      return value;
    } finally {
      end(id);
    }
  }

  function interceptDocumentNavigation() {
    document.addEventListener("submit", (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement) || form.noValidate === false && !form.checkValidity()) return;
      if (form.dataset.loading === "local") return;

      const method = (form.method || "get").toLowerCase();
      if (method === "get" || method === "post") {
        begin({ id: `navigation-form-${Date.now()}`, context: form.dataset.loadingContext || "page", blocking: true });
      }
    });

    document.addEventListener("click", (event) => {
      const link = event.target.closest("a[href]");
      if (!link || event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (link.dataset.loading === "false") return;
      if (link.target && link.target !== "_self") return;

      const href = link.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("javascript:")) return;

      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin) return;

      begin({ id: `navigation-link-${Date.now()}`, context: link.dataset.loadingContext || "page", blocking: true });
    });

    window.addEventListener("beforeunload", () => forceEnd());
    window.addEventListener("pageshow", () => forceEnd());
  }

  function init() {
    ensureMarkup();
    interceptDocumentNavigation();
  }

  window.EasyStoreLoading = Object.freeze({
    begin,
    end,
    track,
    forceEnd,
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
