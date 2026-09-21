(() => {
    const eyeIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-eye"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>`;
    const eyeOffIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-eye-off"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>`;

    const toggles = document.querySelectorAll('.password-toggle');

    toggles.forEach((toggle) => {
        toggle.innerHTML = eyeIcon;

        toggle.addEventListener('click', () => {
            const targetId = toggle.getAttribute('aria-controls');
            if (!targetId) return;

            const input = document.getElementById(targetId);
            if (!input) return;

            const isPasswordHidden = input.type === 'password';
            input.type = isPasswordHidden ? 'text' : 'password';

            toggle.setAttribute('aria-pressed', String(isPasswordHidden));
            toggle.setAttribute('aria-label', isPasswordHidden ? 'Ocultar senha' : 'Mostrar senha');
            toggle.setAttribute('title', isPasswordHidden ? 'Ocultar senha' : 'Mostrar senha');
            toggle.innerHTML = isPasswordHidden ? eyeOffIcon : eyeIcon;
        });
    });

    const forms = document.querySelectorAll('form');

    forms.forEach((form) => {
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

            if (senhaInput && confirmSenhaInput) {
                if (senhaInput.value !== confirmSenhaInput.value) {
                    event.preventDefault();
                    confirmSenhaInput.setCustomValidity('As senhas não coincidem.');
                    confirmSenhaInput.reportValidity();
                    confirmSenhaInput.addEventListener('input', function clearError() {
                        confirmSenhaInput.setCustomValidity('');
                        confirmSenhaInput.removeEventListener('input', clearError);
                    });
                    return;
                }
            }

            form.classList.add('is-submitting');
            submitButton.disabled = true;
            submitButton.textContent = submitButton.textContent === 'Criar conta' ? 'Criando conta...' : 'Entrando...';
        });
    });
})();
