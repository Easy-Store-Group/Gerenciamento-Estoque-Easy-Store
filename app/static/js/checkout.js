// Checkout Button Handler
document.addEventListener('DOMContentLoaded', () => {
    const btnCheckout = document.querySelector('button[type="submit"]');
    
    if (btnCheckout) {
        // Adicionar classe de estilo ao botão
        btnCheckout.classList.add('btn-checkout-finalizar');
        
        // Atualizar ícone e texto
        const originalText = btnCheckout.textContent.trim();
        btnCheckout.innerHTML = '<span class="btn-checkout-icon">🛒</span> ' + (originalText || 'Finalizar Venda');
        
        // Adicionar eventos
        btnCheckout.addEventListener('click', handleCheckoutClick);
        btnCheckout.addEventListener('disabled-change', updateButtonState);
    }
    
    // Listeners para atualizar estado do botão
    const containerCarrinho = document.getElementById('container-itens-carrinho');
    if (containerCarrinho) {
        const observer = new MutationObserver(() => {
            updateCheckoutButtonState();
        });
        observer.observe(containerCarrinho, { childList: true, subtree: true });
    }
});

function handleCheckoutClick(event) {
    const btnCheckout = event.target.closest('button[type="submit"]');
    
    if (!btnCheckout) return;
    
    // Verificar se há itens no carrinho
    const carrinhoJson = document.getElementById('carrinho_json');
    if (!carrinhoJson || !carrinhoJson.value || carrinhoJson.value === '[]') {
        event.preventDefault();
        mostrarAlertaCheckout('Adicione produtos ao carrinho!', 'warning');
        return;
    }
    
    // Adicionar efeito loading
    agendarLoading(btnCheckout);
}

function agendarLoading(btn) {
    btn.classList.add('loading');
    
    // Simular processamento
    setTimeout(() => {
        btn.classList.remove('loading');
    }, 1500);
}

function updateCheckoutButtonState() {
    const btnCheckout = document.querySelector('.btn-checkout-finalizar');
    const carrinhoJson = document.getElementById('carrinho_json');
    
    if (!btnCheckout || !carrinhoJson) return;
    
    const temItens = carrinhoJson.value && carrinhoJson.value !== '[]';
    
    if (!temItens) {
        btnCheckout.disabled = true;
        btnCheckout.style.opacity = '0.5';
        btnCheckout.style.cursor = 'not-allowed';
    } else {
        btnCheckout.disabled = false;
        btnCheckout.style.opacity = '1';
        btnCheckout.style.cursor = 'pointer';
    }
}

function updateButtonState() {
    updateCheckoutButtonState();
}

function mostrarAlertaCheckout(mensagem, tipo = 'info') {
    const alertContainer = document.getElementById('alert-container');
    if (!alertContainer) return;
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${tipo}`;
    alertDiv.textContent = mensagem;
    alertDiv.style.cssText = `
        padding: 12px 16px;
        border-radius: 12px;
        font-size: 13px;
        font-weight: 500;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
        animation: slideIn 0.3s ease-out;
        margin-bottom: 10px;
    `;
    
    // Cores baseadas no tipo
// Cores baseadas no tipo (Paleta em tons azuis)
const cores = {
    success: {
        bg: '#ecfeff',     // Azul Cyan claro
        text: '#155e75',   // Azul Cyan escuro
        border: '#06b6d4'  // Azul Cyan médio
    },
    warning: {
        bg: '#f0f9ff',     // Azul Sky claro
        text: '#0369a1',   // Azul Sky escuro
        border: '#0ea5e9'  // Azul Sky médio
    },
    error: {
        bg: '#eef2ff',     // Azul Indigo claro
        text: '#3730a3',   // Azul Indigo escuro
        border: '#6366f1'  // Azul Indigo médio
    },
    info: {
        bg: '#eff6ff',     // Azul Puro claro
        text: '#1e40af',   // Azul Puro escuro
        border: '#3b82f6'  // Azul Puro médio
    }
};
    
    const cor = cores[tipo] || cores.info;
    alertDiv.style.cssText += `
        background: ${cor.bg};
        color: ${cor.text};
        border-left: 4px solid ${cor.border};
    `;
    
    alertContainer.appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => alertDiv.remove(), 300);
    }, 3000);
}

// Verificar estado inicial
setTimeout(() => {
    updateCheckoutButtonState();
}, 500);

// Monitorar mudanças na visibilidade do botão
const observerBtn = new MutationObserver(() => {
    updateCheckoutButtonState();
});

const btnElement = document.querySelector('button[type="submit"]');
if (btnElement && btnElement.parentElement) {
    observerBtn.observe(btnElement.parentElement, { 
        attributes: true, 
        attributeFilter: ['disabled'] 
    });
}
