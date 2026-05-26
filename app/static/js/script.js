// ============================================
// SMOOTH SCROLL PARA LINKS INTERNOS
// ============================================

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const href = this.getAttribute('href');
        
        // Só fazer scroll suave se o link aponta para um ID na página
        if (href !== '#' && document.querySelector(href)) {
            e.preventDefault();
            
            const element = document.querySelector(href);
            const offset = 70; // Altura do navbar fixo
            const targetPosition = element.offsetTop - offset;
            
            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });
        }
    });
});

// ============================================
// ANIMAÇÃO NAVBAR AO SCROLL
// ============================================

let lastScrollTop = 0;
const navbar = document.querySelector('.navbar');

window.addEventListener('scroll', () => {
    let scrollTop = window.scrollY;
    
    // Adicionar shadow quando scrollar
    if (scrollTop > 10) {
        navbar.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.08)';
    } else {
        navbar.style.boxShadow = 'none';
    }
    
    lastScrollTop = scrollTop;
});

// ============================================
// INTERSECTION OBSERVER PARA ANIMAÇÕES DE ENTRADA
// ============================================

const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            // Adicionar animação ao elemento
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observar cards de features
document.querySelectorAll('.feature-card').forEach(card => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(30px)';
    card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(card);
});

// ============================================
// HOVER EFFECTS PARA BUTTONS
// ============================================

const buttons = document.querySelectorAll('.btn');

buttons.forEach(button => {
    button.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-2px)';
    });
    
    button.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
    });
});

// ============================================
// EFEITO RIPPLE AO CLICAR (OPCIONAL)
// ============================================

function createRipple(event) {
    const button = event.currentTarget;
    const ripple = document.createElement('span');
    
    const rect = button.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;
    
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    ripple.classList.add('ripple');
    
    // Remove ripple anterior se existir
    const existingRipple = button.querySelector('.ripple');
    if (existingRipple) {
        existingRipple.remove();
    }
    
    button.appendChild(ripple);
}

buttons.forEach(button => {
    button.addEventListener('click', createRipple);
});

// ============================================
// DETECÇÃO DE CLIQUE EM BUTTONS PARA MODAL
// ============================================

document.querySelector('.nav-login').addEventListener('click', (e) => {
    e.preventDefault();
    showLoginModal();
});

document.querySelector('.nav-signup').addEventListener('click', (e) => {
    e.preventDefault();
    showSignupModal();
});

document.querySelectorAll('[href="#login"]').forEach(el => {
    el.addEventListener('click', (e) => {
        e.preventDefault();
        showLoginModal();
    });
});

document.querySelectorAll('[href="#signup"]').forEach(el => {
    el.addEventListener('click', (e) => {
        e.preventDefault();
        showSignupModal();
    });
});

// ============================================
// MODAL FUNCTIONS
// ============================================

function showLoginModal() {
    alert('Redirecionando para a página de Login...\n(Integre com seu formulário de login)');
    // Aqui você pode fazer um redirect para a página de login
    // window.location.href = '/login.html';
}

function showSignupModal() {
    alert('Redirecionando para a página de Cadastro...\n(Integre com seu formulário de cadastro)');
    // Aqui você pode fazer um redirect para a página de cadastro
    // window.location.href = '/signup.html';
}

// ============================================
// PARALLAX EFFECT (OPCIONAL)
// ============================================

const heroSection = document.querySelector('.hero');

if (heroSection) {
    window.addEventListener('scroll', () => {
        const scrolled = window.scrollY;
        const gradientElements = heroSection.querySelectorAll('.hero::before, .hero::after');
        
        if (scrolled < window.innerHeight) {
            heroSection.style.backgroundPosition = `0 ${scrolled * 0.5}px`;
        }
    });
}

// ============================================
// PRELOAD IMAGES PARA MELHOR PERFORMANCE
// ============================================

window.addEventListener('load', () => {
    // Otimizações de performance
    document.body.classList.add('loaded');
});

// ============================================
// SUPORTE PARA MODO NOTURNO (FUTURO)
// ============================================

function checkDarkMode() {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        // Usuário prefere modo escuro
        // Você pode implementar um tema escuro aqui se desejar
        console.log('Modo escuro detectado');
    }
}

checkDarkMode();

// ============================================
// EVENT LISTENERS PARA ANALYTICS (EXEMPLO)
// ============================================

// Rastreador de cliques (integre com seu sistema de analytics)
document.querySelectorAll('.btn').forEach(button => {
    button.addEventListener('click', () => {
        const buttonText = button.textContent.trim();
        console.log(`Botão clicado: ${buttonText}`);
        
        // Integre aqui com seu sistema de analytics
        // trackEvent('button_click', { button_name: buttonText });
    });
});

console.log('EasyStore Homepage carregada com sucesso!');




