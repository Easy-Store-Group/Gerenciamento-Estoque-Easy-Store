document.addEventListener('DOMContentLoaded', () => {
  const overlay = document.getElementById('confirm-overlay');
  const messageEl = document.getElementById('confirm-message');
  const titleEl = document.getElementById('confirm-title');
  const btnCancel = document.getElementById('confirm-cancel');
  const btnConfirm = document.getElementById('confirm-confirm');

  if (!overlay || !messageEl || !btnCancel || !btnConfirm) return;

  let resolveCurrent = null;

  function showModal(message, title) {
    titleEl.textContent = title || 'Confirmar ação';
    messageEl.textContent = message || 'Tem certeza que deseja prosseguir?';
    overlay.classList.add('is-open');
    overlay.setAttribute('aria-hidden', 'false');

    return new Promise((resolve) => {
      resolveCurrent = resolve;
      btnConfirm.focus();
    });
  }

  function closeModal() {
    overlay.classList.remove('is-open');
    overlay.setAttribute('aria-hidden', 'true');
    if (resolveCurrent) {
      resolveCurrent = null;
    }
  }

  btnCancel.addEventListener('click', (e) => {
    e.preventDefault();
    if (resolveCurrent) resolveCurrent(false);
    closeModal();
  });

  btnConfirm.addEventListener('click', (e) => {
    e.preventDefault();
    if (resolveCurrent) resolveCurrent(true);
    closeModal();
  });

  // Click outside to cancel
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      if (resolveCurrent) resolveCurrent(false);
      closeModal();
    }
  });

  // Intercept forms with data-confirm
  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', async (e) => {
      // If the form was already confirmed programmatically, allow submission
      if (form.dataset._confirmed === '1') {
        // cleanup flag for future submits
        delete form.dataset._confirmed;
        return;
      }

      e.preventDefault();
      const msg = form.getAttribute('data-confirm') || 'Tem certeza que deseja continuar?';
      const title = form.getAttribute('data-confirm-title') || 'Confirmar ação';
      const ok = await showModal(msg, title);
      if (ok) {
        // mark as confirmed to bypass interceptor and submit
        form.dataset._confirmed = '1';
        form.submit();
      }
    });
  });

  // Intercept links with data-confirm
  document.querySelectorAll('a[data-confirm]').forEach(a => {
    a.addEventListener('click', async (e) => {
      // allow anchors or javascript pseudo-links to pass
      const href = a.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
      e.preventDefault();
      const msg = a.getAttribute('data-confirm') || 'Tem certeza que deseja continuar?';
      const title = a.getAttribute('data-confirm-title') || 'Confirmar ação';
      const ok = await showModal(msg, title);
      if (ok) window.location.href = href;
    });
  });

  // Close modal with Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay.classList.contains('is-open')) {
      if (resolveCurrent) resolveCurrent(false);
      closeModal();
    }
  });

});
