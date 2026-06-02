// PDV - Ponto de Venda - JavaScript
let carrinho = [];
let todosProdutos = [];
let descontoAssociado = 0;

// Elementos do DOM
const inputBusca = document.getElementById('input-busca');
const produtosGrid = document.getElementById('container-itens-carrinho')?.closest('.pdv-grid')?.querySelector('.produtos-grid') || document.querySelector('.produtos-grid');
const containerCarrinho = document.getElementById('container-itens-carrinho');
const clienteSelect = document.getElementById('cliente_id');
const formFinalizar = document.getElementById('form-finalizar');
const carrinhoJsonInput = document.getElementById('carrinho_json');

// Inicializa quando a página carrega
document.addEventListener('DOMContentLoaded', () => {
    inicializarPDV();
    detectarDescontoAssociado();
});

function inicializarPDV() {
    // Captura todos os produtos do template
    document.querySelectorAll('.produto-card-pdv').forEach(card => {
        todosProdutos.push({
            id: parseInt(card.dataset.id),
            nome: card.dataset.nome,
            preco: parseFloat(card.dataset.preco),
            estoque: parseInt(card.dataset.estoque),
            card: card
        });
    });

    // Adicionar evento de click aos cards de produtos
    document.querySelectorAll('.produto-card-pdv').forEach(card => {
        card.addEventListener('click', () => {
            const produtoId = parseInt(card.dataset.id);
            const produto = todosProdutos.find(p => p.id === produtoId);
            if (produto) {
                adicionarAoCarrinho(produto);
            }
        });
        
        // Mostrar cursor de pointer
        card.style.cursor = 'pointer';
    });

    // Busca de produtos
    inputBusca.addEventListener('input', (e) => {
        const termo = e.target.value.toLowerCase();
        filtrarProdutos(termo);
    });

    // Mudança de cliente
    clienteSelect.addEventListener('change', atualizarTotais);

    // Submissão do formulário
    formFinalizar.addEventListener('submit', (e) => {
        e.preventDefault();
        finalizarVenda();
    });

    // F2 para finalizar venda
    document.addEventListener('keydown', (e) => {
        if (e.key === 'F2') {
            e.preventDefault();
            finalizarVenda();
        }
    });

    atualizarCarrinho();
}

function filtrarProdutos(termo) {
    document.querySelectorAll('.produto-card-pdv').forEach(card => {
        const nome = card.dataset.nome.toLowerCase();
        if (nome.includes(termo)) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

function adicionarAoCarrinho(produto) {
    // Verificar se já existe no carrinho
    const itemExistente = carrinho.find(item => item.id === produto.id);
    
    if (itemExistente) {
        if (itemExistente.quantidade < produto.estoque) {
            itemExistente.quantidade++;
        } else {
            mostrarAlerta('Quantidade máxima de estoque atingida!', 'warning');
            return;
        }
    } else {
        carrinho.push({
            ...produto,
            quantidade: 1
        });
    }
    
    atualizarCarrinho();
    mostrarAlerta(`${produto.nome} adicionado ao carrinho!`, 'success');
}

function removerDoCarrinho(produtoId) {
    carrinho = carrinho.filter(item => item.id !== produtoId);
    atualizarCarrinho();
}

function atualizarQuantidade(produtoId, novaQuantidade) {
    const item = carrinho.find(item => item.id === produtoId);
    if (item) {
        const qtd = parseInt(novaQuantidade);
        if (qtd > 0 && qtd <= item.estoque) {
            item.quantidade = qtd;
        } else if (qtd > item.estoque) {
            mostrarAlerta('Quantidade excede o estoque disponível!', 'warning');
            return;
        }
    }
    atualizarCarrinho();
}

function atualizarCarrinho() {
    if (carrinho.length === 0) {
        containerCarrinho.innerHTML = '';
    } else {
        containerCarrinho.innerHTML = carrinho.map(item => `
            <div class="carrinho-itens-item">
                <div class="item-info">
                    <div class="item-nome">${item.nome}</div>
                    <div class="item-qtd">
                        <input type="number" min="1" max="${item.estoque}" value="${item.quantidade}" 
                               onchange="atualizarQuantidade(${item.id}, this.value)" style="width: 50px;">
                    </div>
                </div>
                <div class="item-preco">R$ ${(item.preco * item.quantidade).toFixed(2).replace('.', ',')}</div>
                <button type="button" onclick="removerDoCarrinho(${item.id})" 
                        style="background: none; border: none; color: #dc2626; cursor: pointer; font-weight: bold;">✕</button>
            </div>
        `).join('');
    }
    
    atualizarTotais();
}

function atualizarTotais() {
    const clienteId = parseInt(clienteSelect.value);
    const isAssociado = clienteSelect.options[clienteSelect.selectedIndex]?.dataset.associado === 'true';
    
    let subtotalBruto = carrinho.reduce((sum, item) => sum + (item.preco * item.quantidade), 0);
    let desconto = 0;
    
    if (isAssociado) {
        desconto = subtotalBruto * (descontoAssociado / 100);
    }
    
    let totalLiquido = subtotalBruto - desconto;
    
    document.getElementById('resumo-subtotal').textContent = `R$ ${subtotalBruto.toFixed(2).replace('.', ',')}`;
    document.getElementById('resumo-desconto').textContent = `R$ ${desconto.toFixed(2).replace('.', ',')}`;
    document.getElementById('resumo-total').textContent = `R$ ${totalLiquido.toFixed(2).replace('.', ',')}`;
    
    carrinhoJsonInput.value = JSON.stringify(carrinho);
}

function detectarDescontoAssociado() {
    // Extrair desconto de um dos options
    const firstOption = clienteSelect.querySelector('option[data-associado]');
    if (firstOption) {
        // Procurar por padrão "(Associado -X%)" no texto
        const match = clienteSelect.textContent.match(/Associado -(\d+)%/);
        if (match) {
            descontoAssociado = parseFloat(match[1]);
        }
    }
}

function mostrarAlerta(mensagem, tipo = 'success') {
    const alertContainer = document.getElementById('alert-container');
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${tipo}`;
    alertDiv.textContent = mensagem;
    alertDiv.style.animation = 'slideIn 0.3s ease-out';
    
    alertContainer.appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => alertDiv.remove(), 300);
    }, 3000);
}

function finalizarVenda() {
    if (carrinho.length === 0) {
        mostrarAlerta('Carrinho vazio! Adicione produtos.', 'warning');
        return;
    }
    
    // Atualizar o JSON do carrinho antes de submeter
    carrinhoJsonInput.value = JSON.stringify(carrinho);
    
    // Submeter o formulário
    formFinalizar.submit();
}

// Estilos para animação de alerta
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100%);
        }
    }
`;
document.head.appendChild(style);
