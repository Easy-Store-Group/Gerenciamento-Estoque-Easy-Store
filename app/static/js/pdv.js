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
    carregarDescontoAssociado();
    exibirErroDaUrl();
    inicializarPDV();
    configurarAtalhosTeclado();
});

function configurarAtalhosTeclado() {
    document.addEventListener('keydown', (e) => {
        // F2 para finalizar venda
        if (e.key === 'F2') {
            e.preventDefault();
            finalizarVenda();
        }
        // Escape para limpar busca
        if (e.key === 'Escape' && document.activeElement === inputBusca) {
            inputBusca.value = '';
            filtrarProdutos('');
        }
        // Enter na busca para focar no primeiro produto
        if (e.key === 'Enter' && document.activeElement === inputBusca) {
            const primeiro = document.querySelector('.produto-card-pdv:not([style*="display: none"])');
            if (primeiro) {
                primeiro.click();
            }
        }
    });
}

function inicializarPDV() {
    document.querySelectorAll('.produto-card-pdv').forEach(card => {
        const produtoId = Number(card.dataset.id);
        if (!produtoId) return;

        todosProdutos.push({
            produto_id: produtoId,
            nome: card.dataset.nome,
            preco: parseFloat(card.dataset.preco),
            estoque: parseInt(card.dataset.estoque, 10),
            card: card
        });
    });

    document.querySelectorAll('.produto-card-pdv').forEach(card => {
        card.addEventListener('click', () => {
            const produtoId = Number(card.dataset.id);
            const produto = todosProdutos.find(p => p.produto_id === produtoId);
            if (produto) {
                adicionarAoCarrinho(produto);
            }
        });

        // Keyboard support
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                card.click();
            }
        });

        card.style.cursor = 'pointer';
    });

    inputBusca.addEventListener('input', (e) => {
        const termo = e.target.value.toLowerCase();
        filtrarProdutos(termo);
    });

    clienteSelect.addEventListener('change', atualizarTotais);

    formFinalizar.addEventListener('submit', (e) => {
        e.preventDefault();
        finalizarVenda();
    });

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
        card.style.display = nome.includes(termo) ? '' : 'none';
    });
}

function adicionarAoCarrinho(produto) {
    const itemExistente = carrinho.find(item => item.produto_id === produto.produto_id);

    if (itemExistente) {
        if (itemExistente.quantidade < produto.estoque) {
            itemExistente.quantidade++;
        } else {
            mostrarAlerta('Sem estoque para adicionar mais.', 'warning');
            return;
        }
    } else {
        carrinho.push({
            produto_id: produto.produto_id,
            nome: produto.nome,
            preco: produto.preco,
            estoque: produto.estoque,
            quantidade: 1
        });
    }

    atualizarCarrinho();
    mostrarAlerta(`${produto.nome} adicionado`, 'success', 2500);
}

function removerDoCarrinho(produtoId) {
    carrinho = carrinho.filter(item => item.produto_id !== produtoId);
    atualizarCarrinho();
}

function atualizarQuantidade(produtoId, novaQuantidade) {
    const item = carrinho.find(item => item.produto_id === produtoId);
    if (!item) return;

    const qtd = parseInt(novaQuantidade, 10);
    if (qtd > 0 && qtd <= item.estoque) {
        item.quantidade = qtd;
    } else if (qtd > item.estoque) {
        mostrarAlerta('Estoque insuficiente.', 'warning');
        return;
    } else if (qtd <= 0) {
        removerDoCarrinho(produtoId);
        return;
    }

    atualizarCarrinho();
}

function incrementarQuantidade(produtoId) {
    const item = carrinho.find(item => item.produto_id === produtoId);
    if (!item) return;
    if (item.quantidade < item.estoque) {
        item.quantidade++;
        atualizarCarrinho();
    }
}

function decrementarQuantidade(produtoId) {
    const item = carrinho.find(item => item.produto_id === produtoId);
    if (!item) return;
    if (item.quantidade > 1) {
        item.quantidade--;
        atualizarCarrinho();
    } else {
        removerDoCarrinho(produtoId);
    }
}

function atualizarCarrinho() {
    if (carrinho.length === 0) {
        containerCarrinho.innerHTML = '<div style="color: #999; font-size: 12px; text-align: center; padding: 20px 0;">Nenhum produto adicionado</div>';
    } else {
        containerCarrinho.innerHTML = carrinho.map(item => `
            <div class="carrinho-itens-item">
                <div class="item-info">
                    <div class="item-nome">${item.nome}</div>
                    <div class="item-qtd">
                        <button type="button" class="qtd-btn" onclick="decrementarQuantidade(${item.produto_id})">−</button>
                        <input type="number" min="1" max="${item.estoque}" value="${item.quantidade}"
                               onchange="atualizarQuantidade(${item.produto_id}, this.value)">
                        <button type="button" class="qtd-btn" onclick="incrementarQuantidade(${item.produto_id})">+</button>
                    </div>
                </div>
                <div class="item-preco">R$ ${(item.preco * item.quantidade).toFixed(2).replace('.', ',')}</div>
                <button type="button" class="item-remover" onclick="removerDoCarrinho(${item.produto_id})">×</button>
            </div>
        `).join('');
    }

    atualizarTotais();
}

function atualizarTotais() {
    const isAssociado = clienteSelect.options[clienteSelect.selectedIndex]?.dataset.associado === 'true';

    let subtotalBruto = carrinho.reduce((sum, item) => sum + (item.preco * item.quantidade), 0);
    let desconto = isAssociado ? subtotalBruto * (descontoAssociado / 100) : 0;
    let totalLiquido = subtotalBruto - desconto;

    document.getElementById('resumo-subtotal').textContent = `R$ ${subtotalBruto.toFixed(2).replace('.', ',')}`;
    document.getElementById('resumo-desconto').textContent = `R$ ${desconto.toFixed(2).replace('.', ',')}`;
    document.getElementById('resumo-total').textContent = `R$ ${totalLiquido.toFixed(2).replace('.', ',')}`;
    document.getElementById('carrinho-count').textContent = carrinho.length;

    const linhaDesconto = document.getElementById('linha-desconto');
    if (linhaDesconto) {
        linhaDesconto.style.display = desconto > 0 ? '' : 'none';
    }

    if (carrinhoJsonInput) {
        carrinhoJsonInput.value = serializarCarrinho();
    }
}

function serializarCarrinho() {
    return JSON.stringify(
        carrinho.map(item => ({
            produto_id: item.produto_id,
            quantidade: item.quantidade
        }))
    );
}

function carregarDescontoAssociado() {
    const wrapper = document.querySelector('.pdv-wrapper');
    const valor = parseFloat(wrapper?.dataset.descontoAssociado);
    if (!Number.isNaN(valor)) {
        descontoAssociado = valor;
    }
}

function exibirErroDaUrl() {
    const params = new URLSearchParams(window.location.search);
    const erro = params.get('erro');
    if (!erro) return;

    const mensagens = {
        json: 'Carrinho inválido. Tente novamente.',
        vazio: 'Adicione produtos antes de finalizar.',
        item_invalido: 'Um item inválido foi removido.',
        quantidade: 'Verifique as quantidades.',
        produto_inexistente: `Produto não encontrado.`,
        estoque: `Sem estoque para "${params.get('produto') || 'produto'}".`,
        salvar: 'Erro ao salvar. Tente novamente.',
    };

    mostrarAlerta(mensagens[erro] || 'Erro ao finalizar.', 'warning');

    const url = new URL(window.location.href);
    url.search = '';
    window.history.replaceState({}, '', url);
}

function mostrarAlerta(mensagem, tipo = 'success', duracao = 3000) {
    const alertContainer = document.getElementById('alert-container');
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${tipo}`;
    alertDiv.textContent = mensagem;
    alertDiv.style.animation = 'slideIn 0.3s ease-out';

    alertContainer.appendChild(alertDiv);

    setTimeout(() => {
        alertDiv.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => alertDiv.remove(), 300);
    }, duracao);
}

async function finalizarVenda() {
    if (carrinho.length === 0) {
        mostrarAlerta('Adicione produtos ao carrinho.', 'warning');
        return;
    }

    const payload = serializarCarrinho();
    if (carrinhoJsonInput) {
        carrinhoJsonInput.value = payload;
    }

    const formData = new FormData(formFinalizar);
    formData.set('carrinho_json', payload);

    const btn = formFinalizar.querySelector('button[type="submit"]');
    if (btn) btn.disabled = true;

    try {
        const response = await fetch(formFinalizar.action, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
            redirect: 'follow',
        });

        window.location.href = response.url;
    } catch (error) {
        mostrarAlerta('Erro ao finalizar venda. Tente novamente.', 'warning');
        if (btn) btn.disabled = false;
    }
}
