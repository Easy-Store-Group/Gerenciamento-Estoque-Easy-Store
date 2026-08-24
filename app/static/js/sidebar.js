(function () {
  const breakpoint = 820;

  function getSidebar() {
    return document.querySelector('[data-sidebar]');
  }

  function getToggle() {
    return document.querySelector('[data-sidebar-toggle]');
  }

  function getBackdrop() {
    return document.querySelector('[data-sidebar-backdrop]');
  }

  function isMobile() {
    return window.matchMedia(`(max-width: ${breakpoint}px)`).matches;
  }

  function setExpanded(toggle, expanded) {
    if (!toggle) return;
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.setAttribute('aria-label', expanded ? 'Fechar menu principal' : 'Abrir menu principal');
  }

  function openSidebar() {
    const sidebar = getSidebar();
    const toggle = getToggle();
    const backdrop = getBackdrop();
    if (!sidebar || !toggle || !backdrop) return;

    document.body.classList.add('sidebar-open');
    sidebar.classList.add('is-open');
    backdrop.hidden = false;
    backdrop.classList.add('is-open');
    setExpanded(toggle, true);
  }

  function closeSidebar() {
    const sidebar = getSidebar();
    const toggle = getToggle();
    const backdrop = getBackdrop();
    if (!sidebar || !toggle || !backdrop) return;

    document.body.classList.remove('sidebar-open');
    sidebar.classList.remove('is-open');
    backdrop.classList.remove('is-open');
    backdrop.hidden = true;
    setExpanded(toggle, false);
  }

  function toggleSidebar() {
    const sidebar = getSidebar();
    if (!sidebar) return;
    if (sidebar.classList.contains('is-open')) {
      closeSidebar();
    } else {
      openSidebar();
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const sidebar = getSidebar();
    const toggle = getToggle();
    const backdrop = getBackdrop();

    if (!sidebar || !toggle || !backdrop) return;

    setExpanded(toggle, false);
    backdrop.hidden = true;

    toggle.addEventListener('click', toggleSidebar);
    backdrop.addEventListener('click', closeSidebar);

    sidebar.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        if (isMobile()) closeSidebar();
      });
    });

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && sidebar.classList.contains('is-open')) {
        closeSidebar();
        toggle.focus();
      }
    });

    window.addEventListener('resize', () => {
      if (!isMobile()) {
        closeSidebar();
      }
    });
  });
})();
