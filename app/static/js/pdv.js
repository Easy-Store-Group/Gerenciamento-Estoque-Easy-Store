// PDV - Ponto de Venda - JavaScript
let carrinho = [];
let todosProdutos = [];
let descontoAssociado = 0;
let produtoSelecionado = null;
let variacoesProduto = [];

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
});

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
        card.addEventListener('click', async () => {
            const produtoId = Number(card.dataset.id);
            const produto = todosProdutos.find(p => p.produto_id === produtoId);
            if (produto) {
                // Carrega variações do produto
                await carregarVariacoesPDV(produto);
            }
        });
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
async function carregarVariacoesPDV(produto) {
    try {
        const response = await fetch(`/api/variacoes/produto/${produto.produto_id}`);
        if (!response.ok) {
            // Sem variações, adiciona direto
            adicionarAoCarrinho(produto);
            return;
        }

        variacoesProduto = await response.json();
        
        if (variacoesProduto.length === 0) {
            // Sem variações, adiciona direto
            adicionarAoCarrinho(produto);
            return;
        }

        // Tem variações, mostra modal
        produtoSelecionado = produto;
        abrirModalVariacoes(produto, variacoesProduto);
        
    } catch (error) {
        console.error('Erro ao carregar variações:', error);
        adicionarAoCarrinho(produto);
    }
}
function abrirModalVariacoes(produto, variacoes) {
    const modal = document.getElementById('modal-variacoes');
    const titulo = document.getElementById('modal-titulo');
    const corpo = document.getElementById('modal-corpo');

    titulo.textContent = `Selecione variações para: ${produto.nome}`;
    
    let html = '';

    // Agrupa variações por tipo
    const cores = new Set();
    const tamanhos = new Set();
    
    variacoes.forEach(v => {
        if (v.cor) cores.add(JSON.stringify(v.cor));
        if (v.tamanho) tamanhos.add(JSON.stringify(v.tamanho));
    });

    // Seleto de tamanhos
    if (tamanhos.size > 0) {
        html += '<div class="form-group-modal">';
        html += '<label for="select-tamanho-pdv">Tamanho</label>';
        html += '<select id="select-tamanho-pdv" class="form-control">';
        html += '<option value="">-- Selecione um tamanho --</option>';
        
        Array.from(tamanhos).forEach(t => {
            const tamanho = JSON.parse(t);
            html += `<option value="${tamanho.id}">${tamanho.nome}</option>`;
        });
        
        html += '</select></div>';
    }

    // Seleto de cores
    if (cores.size > 0) {
        html += '<div class="form-group-modal">';
        html += '<label for="select-cor-pdv">Cor</label>';
        html += '<select id="select-cor-pdv" class="form-control">';
        html += '<option value="">-- Selecione uma cor --</option>';
        
        Array.from(cores).forEach(c => {
            const cor = JSON.parse(c);
            html += `<option value="${cor.id}">${cor.nome}</option>`;
        });
        
        html += '</select></div>';
    }

    corpo.innerHTML = html;
    modal.classList.add('is-open');
}

function fecharModalVariacoes() {
    document.getElementById('modal-variacoes').classList.remove('is-open');
    produtoSelecionado = null;
}

function confirmarVariacoes() {
    if (!produtoSelecionado) return;

    const tamanhoId = document.getElementById('select-tamanho-pdv')?.value;
    const corId = document.getElementById('select-cor-pdv')?.value;

    // Encontra a variação correspondente
    const variacao = variacoesProduto.find(v => {
        const tempoMesmaTamanho = !tamanhoId || (v.tamanho && v.tamanho.id === parseInt(tamanhoId));
        const tempoMesmaCor = !corId || (v.cor && v.cor.id === parseInt(corId));
        return tempoMesmaTamanho && tempoMesmaCor;
    });

    if (!variacao) {
        mostrarAlerta('Selecione uma combinação válida de cor e tamanho', 'warning');
        return;
    }

    // Adiciona ao carrinho com variação
    adicionarAoCarrinho(produtoSelecionado, variacao);
    fecharModalVariacoes();
}

function filtrarProdutos(termo) {
    document.querySelectorAll('.produto-card-pdv').forEach(card => {
        const nome = card.dataset.nome.toLowerCase();
        card.style.display = nome.includes(termo) ? '' : 'none';
    });
}

function adicionarAoCarrinho(produto, variacao = null) {
    const descricaoVariacao = variacao ? ` [${variacao.cor ? variacao.cor.nome : ''}${variacao.tamanho ? ' - ' + variacao.tamanho.nome : ''}]` : '';
    const chaveItem = `${produto.produto_id}${variacao ? '_' + variacao.id : ''}`;
    
    const itemExistente = carrinho.find(item => item.chave === chaveItem);

    if (itemExistente) {
        if (itemExistente.quantidade < produto.estoque) {
            itemExistente.quantidade++;
        } else {
            mostrarAlerta('Quantidade máxima de estoque atingida!', 'warning');
            return;
        }
    } else {
        carrinho.push({
            chave: chaveItem,
            produto_id: produto.produto_id,
            variacao_id: variacao?.id || null,
            nome: produto.nome + descricaoVariacao,
            preco: produto.preco,
            estoque: produto.estoque,
            quantidade: 1
        });
    }

    atualizarCarrinho();
    mostrarAlerta(`${produto.nome} adicionado ao carrinho!`, 'success');
}

function removerDoCarrinho(chaveItem) {
    carrinho = carrinho.filter(item => item.chave !== chaveItem);
    atualizarCarrinho();
}

function atualizarQuantidade(chaveItem, novaQuantidade) {
    const item = carrinho.find(item => item.chave === chaveItem);
    if (!item) return;

    const qtd = parseInt(novaQuantidade, 10);
    if (qtd > 0 && qtd <= item.estoque) {
        item.quantidade = qtd;
    } else if (qtd > item.estoque) {
        mostrarAlerta('Quantidade excede o estoque disponível!', 'warning');
        return;
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
                        <input type="number" class="item-quantidade" min="1" max="${item.estoque}" value="${item.quantidade}"
                               onchange="atualizarQuantidade('${item.chave}', this.value)">
                    </div>
                </div>
                <div class="item-preco">R$ ${(item.preco * item.quantidade).toFixed(2).replace('.', ',')}</div>
                <button type="button" class="btn-remover-item" onclick="removerDoCarrinho('${item.chave}')" aria-label="Remover item">&times;</button>
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

    if (carrinhoJsonInput) {
        carrinhoJsonInput.value = serializarCarrinho();
    }
}

function serializarCarrinho() {
    return JSON.stringify(
        carrinho.map(item => ({
            produto_id: item.produto_id,
            variacao_id: item.variacao_id,
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
        json: 'Carrinho inválido. Tente adicionar os produtos novamente.',
        vazio: 'O carrinho está vazio. Adicione produtos antes de finalizar.',
        item_invalido: 'Um ou mais itens do carrinho estão inválidos.',
        quantidade: 'Quantidade inválida em um dos itens.',
        produto_inexistente: `Produto #${params.get('id') || '?'} não encontrado ou inativo.`,
        estoque: `Estoque insuficiente para "${params.get('produto') || 'produto'}".`,
        salvar: 'Não foi possível salvar a venda. Tente novamente.',
    };

    mostrarAlerta(mensagens[erro] || 'Ocorreu um erro ao finalizar a venda.', 'warning');

    const url = new URL(window.location.href);
    url.search = '';
    window.history.replaceState({}, '', url);
}

function mostrarAlerta(mensagem, tipo = 'success') {
    const alertContainer = document.getElementById('alert-container');
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${tipo}`;
    alertDiv.textContent = mensagem;
    alertDiv.classList.add('alert-enter');

    alertContainer.appendChild(alertDiv);

    setTimeout(() => {
        alertDiv.classList.remove('alert-enter');
        alertDiv.classList.add('alert-exit');
        setTimeout(() => alertDiv.remove(), 300);
    }, 3000);
}

async function finalizarVenda() {
    if (carrinho.length === 0) {
        mostrarAlerta('Carrinho vazio! Adicione produtos.', 'warning');
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
