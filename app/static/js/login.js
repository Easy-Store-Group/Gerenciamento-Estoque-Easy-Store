(() => {
    // Toggle any password inputs referenced by .password-toggle buttons
    const toggles = document.querySelectorAll('.password-toggle');
    toggles.forEach(toggle => {
        toggle.addEventListener('click', () => {
            const targetId = toggle.getAttribute('aria-controls');
            if (!targetId) return;
            const input = document.getElementById(targetId);
            if (!input) return;
            const show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            toggle.setAttribute('aria-pressed', String(show));
            toggle.textContent = show ? 'Ocultar senha' : 'Mostrar senha';
        });
    });

    // Keep previous login form submit behavior if present
    const loginForm = document.getElementById('login-form');
    const submitButton = loginForm?.querySelector('button[type="submit"]');
    if (loginForm && submitButton) {
        loginForm.addEventListener('submit', () => {
            if (!loginForm.checkValidity()) return;
            loginForm.classList.add('is-submitting');
            submitButton.disabled = true;
            submitButton.textContent = 'Entrando...';
        });
    }
})();
