(() => {
    const eyeIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>`;
    const eyeOffIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>`;

    document.querySelectorAll('.password-toggle').forEach((toggle) => {
        toggle.innerHTML = eyeIcon;

        toggle.addEventListener('click', () => {
            const targetId = toggle.getAttribute('aria-controls');
            const input = targetId ? document.getElementById(targetId) : null;
            if (!input) return;

            const willShowPassword = input.type === 'password';
            input.type = willShowPassword ? 'text' : 'password';

            toggle.setAttribute('aria-pressed', String(willShowPassword));
            toggle.setAttribute('aria-label', willShowPassword ? 'Ocultar senha' : 'Mostrar senha');
            toggle.setAttribute('title', willShowPassword ? 'Ocultar senha' : 'Mostrar senha');
            toggle.innerHTML = willShowPassword ? eyeOffIcon : eyeIcon;
            input.focus({ preventScroll: true });
        });
    });

    document.querySelectorAll('form').forEach((form) => {
        const submitButton = form.querySelector('button[type="submit"]');
        if (!submitButton) return;

        form.addEventListener('submit', (event) => {
            if (!form.checkValidity()) {
                event.preventDefault();
                form.reportValidity();
                return;
            }

            const senhaInput = form.querySelector('#senha');
            const confirmSenhaInput = form.querySelector('#confirmar_senha');

            if (senhaInput && confirmSenhaInput && senhaInput.value !== confirmSenhaInput.value) {
                event.preventDefault();
                confirmSenhaInput.setCustomValidity('As senhas não coincidem.');
                confirmSenhaInput.reportValidity();
                confirmSenhaInput.addEventListener('input', function clearError() {
                    confirmSenhaInput.setCustomValidity('');
                    confirmSenhaInput.removeEventListener('input', clearError);
                });
                return;
            }

            form.classList.add('is-submitting');
            submitButton.disabled = true;
            submitButton.textContent = submitButton.textContent.trim() === 'Criar conta' ? 'Criando conta...' : 'Entrando...';
        });
    });
})();
