/* ============================================
   EASYSTORE - ANIMAÇÕES E INTERAÇÕES (produtos.js)
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {
    initCategorySelection();
    initScrollReveal();
    initButtonEffects();
    initResponsiveSidebar();
});

/* ============================================
   1. SELEÇÃO DE CATEGORIAS (SIDEBAR)
   ============================================ */
function initCategorySelection() {
    const sideItems = document.querySelectorAll('.side-item');

    sideItems.forEach(item => {
        item.addEventListener('click', (e) => {
            // Remove a classe active de todos os botões
            sideItems.forEach(btn => btn.classList.remove('active'));

            // Adiciona a classe active ao botão clicado
            e.currentTarget.classList.add('active');

            // Feedback visual suave de clique (Micro-interação)
            animateClick(e.currentTarget);

            // Centraliza o item na barra horizontal em dispositivos móveis
            centerMobileSidebarItem(e.currentTarget);
        });
    });
}

/* ============================================
   2. REVELAÇÃO SUAVE AO ROLAR (SCROLL REVEAL)
   ============================================ */
function initScrollReveal() {
    // Seleciona as seções principais para animar a entrada
    const targetSections = document.querySelectorAll('.hero, .featured, .wishlist');

    // Configuração do Intersection Observer para disparar quando 10% do item surgir
    const observerOptions = {
        root: null,
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const revealObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // Aplica estilos de transição fluida nativa via JS
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                // Para de observar o elemento após a animação acontecer
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Estado inicial oculto antes da animação
    targetSections.forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(40px)';
        section.style.transition = 'opacity 0.8s cubic-bezier(0.4, 0, 0.2, 1), transform 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
        revealObserver.observe(section);
    });
}

/* ============================================
   3. MICRO-INTERAÇÕES NOS BOTÕES
   ============================================ */
function initButtonEffects() {
    const allButtons = document.querySelectorAll('.btn-primary, .btn-outline, .side-item');

    allButtons.forEach(button => {
        // Efeito Magnético Sutil ao passar o mouse
        button.addEventListener('mousemove', (e) => {
            const rect = button.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;

            // Move levemente o botão na direção do cursor do usuário
            button.style.transform = `translate(${x * 0.15}px, ${y * 0.15}px) scale(1.02)`;
        });

        // Restaura a posição original quando o mouse sai
        button.addEventListener('mouseleave', () => {
            button.style.transform = '';
        });
    });
}

// Animação de escala rápida ao clicar
function animateClick(element) {
    element.style.transform = 'scale(0.95)';
    setTimeout(() => {
        element.style.transform = '';
    }, 150);
}

/* ============================================
   4. INTELIGÊNCIA DE RESPONSIVIDADE (MOBILE)
   ============================================ */
function centerMobileSidebarItem(activeItem) {
    // Aplica o comportamento apenas se a tela for menor que a quebra de layout do CSS (992px)
    if (window.innerWidth <= 992) {
        const sidebar = document.querySelector('.sidebar');
        if (!sidebar) return;

        // Calcula a posição para centralizar o botão clicado na barra horizontal rolável
        const sidebarWidth = sidebar.offsetWidth;
        const itemOffsetLeft = activeItem.offsetLeft;
        const itemWidth = activeItem.offsetWidth;

        const scrollTarget = itemOffsetLeft - (sidebarWidth / 2) + (itemWidth / 2);

        // Realiza uma rolagem horizontal suaveizada
        sidebar.scrollTo({
            left: scrollTarget,
            behavior: 'smooth'
        });
    }
}

function initResponsiveSidebar() {
    // Otimiza o comportamento de redimensionamento de janela (Debounce simples)
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            const sidebar = document.querySelector('.sidebar');
            const activeItem = document.querySelector('.side-item.active');

            // Se voltou para o desktop, limpa resquícios de scrolls manuais mobiles
            if (window.innerWidth > 992 && sidebar) {
                sidebar.scrollLeft = 0;
            } else if (activeItem) {
                centerMobileSidebarItem(activeItem);
            }
        }, 100);
    });
}

function initCategorySelection() {
    const sideItems = document.querySelectorAll('.side-item');

    sideItems.forEach(item => {
        item.addEventListener('click', (e) => {
            // Remove o estado ativo visual e semântico de TODOS os botões
            sideItems.forEach(btn => {
                btn.classList.remove('active');
                btn.setAttribute('aria-pressed', 'false');
            });

            // Ativa o botão que acabou de ser clicado
            const clickedButton = e.currentTarget;
            clickedButton.classList.add('active');
            clickedButton.setAttribute('aria-pressed', 'true');

            // Mantém as animações fluidas que já criamos
            animateClick(clickedButton);
            centerMobileSidebarItem(clickedButton);
        });
    });
}