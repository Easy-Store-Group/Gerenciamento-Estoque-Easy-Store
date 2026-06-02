/**
 * SISTEMA DE PDV — CONTROLE OPERACIONAL DO CARRINHO
 * Sincronizado com FastAPI + SQLAlchemy
 */

// 1. CONFIGURAÇÕES E ESTADO GLOBAL
// Busca o valor do desconto injetado no elemento HTML de configuração
const obterDescontoMinimo = () => {
    const elemento = document.getElementById('config-desconto');
    return elemento ? parseFloat(elemento.dataset.desconto) : 0;
};

let carrinho = [];

// Recuperação segura do sessionStorage ao iniciar a página
try {
    carrinho = JSON.parse(sessionStorage.getItem('carrinho')) || [];
} catch (e) {
    console.error("Erro ao ler o sessionStorage, reiniciando carrinho:", e);
    carrinho = [];
}

// 2. CAPTURA DE ERROS DA URL (RETORNO DO BACKEND)
const processarErrosURL = () => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('erro')) {
        const erro = urlParams.get('erro');
        const container = document.getElementById('alert-container');
        
        if (container) {
            let mensagem = "Ocorreu um erro ao processar a venda.";
            if (erro === 'vazio') mensagem = "⚠️ O carrinho não pode estar vazio para finalizar a venda.";
            if (erro === 'quantidade') mensagem = "⚠️ Quantidade inválida de itens informada.";
            if (erro === 'estoque') mensagem = `❌ Estoque insuficiente para o produto: ${urlParams.get('produto') || 'solicitado'}.`;
            if (erro === 'produto_inexistente') mensagem = "❌ Um ou mais produtos do carrinho não foram localizados.";
            if (erro === 'json') mensagem = "❌ Erro na integridade dos dados enviados.";

            container.innerHTML = `<div class="alert alert-danger">${mensagem}</div>`;
        }
    }
};

// 3. FUNÇÕES DE MANIPULAÇÃO DO CARRINHO
function adicionarAoCarrinho(id, nome, preco, estoqueMax) {
    const itemExistente = carrinho.find(item => item.produto_id === id);

    if (itemExistente) {
        if (itemExistente.quantidade < estoqueMax) {
            itemExistente.quantidade++;
        } else {
            alert(`Quantidade máxima em estoque atingida para este produto (${estoqueMax} un).`);
            return;
        }
    } else {
        if (estoqueMax <= 0) {
            alert("Este produto está esgotado no momento.");
            return;
        }
        carrinho.push({
            produto_id: id,
            nome: nome,
            preco: preco,
            quantidade: 1,
            estoque_max: estoqueMax
        });
    }
    salvarERenderizar();
}

function alterarQuantidade(id, delta) {
    const item = carrinho.find(item => item.produto_id === id);
    if (!item) return;

    item.quantidade += delta;

    if (item.quantidade <= 0) {
        carrinho = carrinho.filter(i => i.produto_id !== id);
    } else if (item.quantidade > item.estoque_max) {
        alert(`Quantidade máxima em estoque atingida (${item.estoque_max} un).`);
        item.quantidade = item.estoque_max;
    }

    salvarERenderizar();
}

// 4. PERSISTÊNCIA E SINCRONIZAÇÃO COM O FORMULÁRIO
function salvarERenderizar() {
    sessionStorage.setItem('carrinho', JSON.stringify(carrinho));
    
    // Envia apenas o payload que o modelo Pydantic/FastAPI espera receber
    const backendPayload = carrinho.map(i => ({
        produto_id: i.produto_id,
        nome: i.nome,
        preco: i.preco,
        quantidade: i.quantidade
    }));
    
    const inputHidden = document.getElementById('carrinho_json');
    if (inputHidden) {
        inputHidden.value = JSON.stringify(backendPayload);
    }

    renderizarCarrinhoHTML();
    atualizarTotais();
}

function renderizarCarrinhoHTML() {
    const container = document.getElementById('container-itens-carrinho');
    if (!container) return;

    container.innerHTML = '';

    if (carrinho.length === 0) {
        container.innerHTML = '<p style="text-align:center; color:var(--color-gray-dark); margin-top:20px;">Carrinho vazio</p>';
        return;
    }

    carrinho.forEach(item => {
        const itemHtml = `
            <div class="carrinho-item">
                <div class="item-meta">
                    <h5>${item.nome}</h5>
                    <p>R$ ${item.preco.toFixed(2).replace('.', ',')}</p>
                </div>
                <div class="item-controles">
                    <button type="button" class="btn-qtd" onclick="alterarQuantidade(${item.produto_id}, -1)">-</button>
                    <span style="font-weight:600; width:20px; text-align:center;">${item.quantidade}</span>
                    <button type="button" class="btn-qtd" onclick="alterarQuantidade(${item.produto_id}, 1)">+</button>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', itemHtml);
    });
}

function atualizarTotais() {
    let bruto = 0;
    carrinho.forEach(item => {
        bruto += item.preco * item.quantidade;
    });

    const selectCliente = document.getElementById('cliente_id');
    let descPercentualCalculo = 0;

    if (selectCliente && selectCliente.selectedIndex !== -1) {
        const opcaoSelecionada = selectCliente.options[selectCliente.selectedIndex];
        if (opcaoSelecionada && opcaoSelecionada.dataset.associado === 'true') {
            descPercentualCalculo = obterDescontoMinimo();
        }
    }

    let valorDesconto = bruto * (descPercentualCalculo / 100);
    let liquido = bruto - valorDesconto;

    const elemSubtotal = document.getElementById('resumo-subtotal');
    const elemDesconto = document.getElementById('resumo-desconto');
    const elemTotal = document.getElementById('resumo-total');

    if (elemSubtotal) elemSubtotal.innerText = `R$ ${bruto.toFixed(2).replace('.', ',')}`;
    if (elemDesconto) elemDesconto.innerText = `R$ ${valorDesconto.toFixed(2).replace('.', ',')}`;
    if (elemTotal) elemTotal.innerText = `R$ ${liquido.toFixed(2).replace('.', ',')}`;
}

// 5. INICIALIZAÇÃO DE ESCUTADORES DE EVENTOS
document.addEventListener('DOMContentLoaded', () => {
    // Processa erros vindos do backend
    processarErrosURL();

    // Cliques nos cards de produtos
    document.querySelectorAll('.produto-card-pdv').forEach(card => {
        card.addEventListener('click', () => {
            const id = parseInt(card.dataset.id, 10);
            const nome = card.dataset.nome;
            const preco = parseFloat(card.dataset.preco);
            const estoqueMax = parseInt(card.dataset.estoque, 10);

            if (!isNaN(id)) {
                adicionarAoCarrinho(id, nome, preco, estoqueMax);
            }
        });
    });

    // Filtro de Busca em Tempo Real
    const inputBusca = document.getElementById('input-busca');
    if (inputBusca) {
        inputBusca.addEventListener('input', function(e) {
            const termo = e.target.value.toLowerCase().trim();
            document.querySelectorAll('.produto-card-pdv').forEach(card => {
                const nome = card.dataset.nome.toLowerCase();
                card.style.display = nome.includes(termo) ? 'flex' : 'none';
            });
        });
    }

    // Monitoramento do Submit do Formulário
    document.getElementById('form-finalizar')?.addEventListener('submit', function(e) {
        if (carrinho.length === 0) {
            e.preventDefault();
            alert("Não é possível finalizar uma venda sem itens no carrinho.");
            return;
        }
        // Agenda a limpeza do carrinho para após a requisição disparar
        setTimeout(() => sessionStorage.removeItem('carrinho'), 200);
    });

    // Atalhos de Teclado (F2 — Enviar Formulário)
    window.addEventListener('keydown', function(e) {
        if (e.key === 'F2') {
            e.preventDefault();
            const form = document.getElementById('form-finalizar');
            if (form) form.requestSubmit();
        }
    });

    // Renderiza o estado inicial (caso existam itens salvos de outra aba)
    salvarERenderizar();
});