// PDV - Ponto de Venda - JavaScript
let carrinho = [];
let todosProdutos = [];
let descontoAssociado = 0;
let produtoSelecionado = null;
let variacoesProduto = [];
let confirmacaoVendaEmAndamento = false;
let chaveIdempotenciaVenda = null;
let pixConfirmadoVenda = false;
let estadoPagamentoPDV = 'idle';
let cacheVariacoesPDV = new Map();
let variacoesEmAndamento = new Map();
let debounceBuscaPDV = null;

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
    // Habilita submissão do formulário de busca/por_pagina quando existir
    const formBusca = document.querySelector('form.search-box');
    if (formBusca) {
        formBusca.addEventListener('submit', (ev) => {
            ev.preventDefault();
            const params = new URLSearchParams(window.location.search);
            const termo = formBusca.querySelector('input[name="busca"]')?.value || '';
            const porPagina = formBusca.querySelector('select[name="por_pagina"]')?.value || '';
            params.set('busca', termo);
            if (porPagina) params.set('por_pagina', porPagina);
            params.set('pagina', '1');
            window.location.search = params.toString();
        });

        // quando trocar por_pagina, recarrega na página 1
        const sel = formBusca.querySelector('select[name="por_pagina"]');
        if (sel) {
            sel.addEventListener('change', () => formBusca.requestSubmit());
        }
    }

    inicializarPDV();

    const modal = document.getElementById('modal-confirmacao-pagamento');
    const confirmar = document.getElementById('btn-confirmar-pagamento-modal');
    const voltar = document.getElementById('btn-voltar-confirmacao-pagamento');
    const fechar = document.getElementById('btn-fechar-confirmacao-pagamento');

    if (voltar) voltar.addEventListener('click', fecharConfirmacaoPagamento);
    if (fechar) fechar.addEventListener('click', fecharConfirmacaoPagamento);

    if (modal) {
        modal.addEventListener('click', (event) => {
            if (event.target === modal) fecharConfirmacaoPagamento();
        });
    }

    if (confirmar) {
        confirmar.addEventListener('click', async () => {
            if (confirmacaoVendaEmAndamento || confirmar.disabled) return;
            confirmacaoVendaEmAndamento = true;
            confirmar.disabled = true;
            confirmar.textContent = 'Processando...';
            estadoPagamentoPDV = 'processing';

            try {
                await finalizarVenda();
            } finally {
                confirmacaoVendaEmAndamento = false;
                confirmar.disabled = false;
                confirmar.textContent = 'Confirmar pagamento';
            }
        });
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal?.classList.contains('is-open')) {
            event.preventDefault();
            fecharConfirmacaoPagamento();
        }
    });
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

    if (inputBusca) {
        inputBusca.addEventListener('input', (e) => {
            const termo = e.target.value.toLowerCase();
            filtrarProdutos(termo);
            if (debounceBuscaPDV) clearTimeout(debounceBuscaPDV);
            debounceBuscaPDV = setTimeout(() => {
                const termoServidor = e.target.value.trim();
                if (termoServidor.length === 0 || termoServidor.length >= 2) {
                    const params = new URLSearchParams(window.location.search);
                    params.set('busca', termoServidor);
                    params.set('pagina', '1');
                    window.location.search = params.toString();
                }
            }, 350);
        });
    }

    clienteSelect.addEventListener('change', atualizarTotais);

    formFinalizar.addEventListener('submit', (e) => {
        e.preventDefault();
        abrirConfirmacaoPagamento();
    });

    document.addEventListener('keydown', (e) => {
        // Ignora se o foco estiver dentro de um campo de texto ou input
        const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
        const isInput = tag === 'input' || tag === 'textarea' || tag === 'select';

        if (e.key === 'F2') {
            e.preventDefault();
            abrirConfirmacaoPagamento();
        } else if (e.key === 'F4' && !isInput) {
            e.preventDefault();
            limparCarrinhoComConfirmacao();
        } else if (e.key === '/' && !isInput) {
            e.preventDefault();
            if (inputBusca) {
                inputBusca.focus();
                inputBusca.select();
            }
        }
    });

    restaurarCarrinhoPDV();
    atualizarCarrinho();
}
async function carregarVariacoesPDV(produto) {
    const chave = String(produto.produto_id);
    const agora = Date.now();
    const cached = cacheVariacoesPDV.get(chave);

    if (cached && cached.expiraEm > agora) {
        variacoesProduto = cached.valor;
    } else {
        let promise = variacoesEmAndamento.get(chave);
        if (!promise) {
            promise = fetch(`/api/variacoes/produto/${produto.produto_id}`, {
                method: "GET",
                headers: { "Accept": "application/json" },
                credentials: "same-origin",
            }).then(async (response) => {
                if (!response.ok) return null;
                return response.json();
            }).finally(() => {
                variacoesEmAndamento.delete(chave);
            });
            variacoesEmAndamento.set(chave, promise);
        }

        try {
            const resultado = await promise;
            if (resultado === null) {
                adicionarAoCarrinho(produto);
                return;
            }
            variacoesProduto = resultado;
            cacheVariacoesPDV.set(chave, {
                valor: variacoesProduto,
                expiraEm: Date.now() + 10000,
            });
        } catch (error) {
            console.error('Erro ao carregar variações:', error);
            adicionarAoCarrinho(produto);
            return;
        }
    }

    if (variacoesProduto.length === 0) {
        adicionarAoCarrinho(produto);
        return;
    }

    produtoSelecionado = produto;
    abrirModalVariacoes(produto, variacoesProduto);
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
    const estoqueDisponivel = variacao && typeof variacao.estoque_atual === 'number' ? variacao.estoque_atual : produto.estoque;
    
    const itemExistente = carrinho.find(item => item.chave === chaveItem);

    if (itemExistente) {
        if (itemExistente.quantidade < estoqueDisponivel) {
            itemExistente.quantidade++;
        } else {
            mostrarAlerta(`Quantidade máxima de estoque atingida (${estoqueDisponivel} un)!`, 'warning');
            return;
        }
    } else {
        if (estoqueDisponivel <= 0) {
            mostrarAlerta('Produto sem estoque disponível no momento.', 'warning');
            return;
        }
        carrinho.push({
            chave: chaveItem,
            produto_id: produto.produto_id,
            variacao_id: variacao?.id || null,
            nome: produto.nome + descricaoVariacao,
            preco: variacao?.preco ?? produto.preco,
            estoque: estoqueDisponivel,
            quantidade: 1
        });
    }

    atualizarCarrinho();
    mostrarAlerta(`${produto.nome}${descricaoVariacao} adicionado ao carrinho!`, 'success');
}

function removerDoCarrinho(chaveItem) {
    const item = carrinho.find(i => i.chave === chaveItem);
    carrinho = carrinho.filter(i => i.chave !== chaveItem);
    atualizarCarrinho();
    if (item) {
        mostrarAlerta(`"${item.nome}" removido do carrinho.`, 'info');
    }
}

function limparCarrinhoComConfirmacao() {
    if (carrinho.length === 0) {
        mostrarAlerta('O carrinho já está vazio.', 'info');
        return;
    }
    if (confirm('Deseja realmente cancelar a venda e esvaziar o carrinho? O estoque não sofrerá alterações.')) {
        carrinho = [];
        atualizarCarrinho();
        mostrarAlerta('Venda cancelada. Carrinho esvaziado com sucesso.', 'info');
        pixConfirmadoVenda = false;
        chaveIdempotenciaVenda = null;
    }
}

function atualizarQuantidade(chaveItem, novaQuantidade) {
    const item = carrinho.find(item => item.chave === chaveItem);
    if (!item) return;

    const qtd = parseInt(novaQuantidade, 10);
    if (qtd > 0 && qtd <= item.estoque) {
        item.quantidade = qtd;
    } else if (qtd > item.estoque) {
        item.quantidade = item.estoque;
        mostrarAlerta(`Quantidade solicitada excede o estoque disponível (${item.estoque} un)! Ajustado para o máximo.`, 'warning');
    } else {
        removerDoCarrinho(chaveItem);
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
    salvarCarrinhoPDV();
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
        pix_indisponivel: 'PIX temporariamente indisponível. Não foi possível estabelecer conexão com o serviço de pagamento. Escolha outra forma de pagamento ou tente novamente mais tarde.',
        forma_pagamento: 'Selecione uma forma de pagamento.',
        forma_pagamento_invalida: 'Forma de pagamento inválida.',
        valor_recebido: 'Informe o valor recebido para o pagamento em dinheiro.',
        valor_insuficiente: 'O valor informado é menor que o total da venda.',
        valor_pagamento_invalido: 'Informe valores válidos para cada método de pagamento.',
        pagamento_duplicado: 'Não é permitido repetir a mesma forma de pagamento na mesma venda.',
        pix_nao_confirmado: 'Confirme o recebimento do PIX antes de finalizar a venda.',
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

function formatarMetodoPagamento(forma) {
    const nomes = {
        dinheiro: "Dinheiro",
        pix: "PIX",
        cartao_credito: "Cartão de crédito",
        cartao_debito: "Cartão de débito",
    };
    return nomes[forma] || "Pagamento";
}

function formatarMoeda(valor) {
    const numero = Number(valor);
    const seguro = Number.isFinite(numero) ? numero : 0;
    return `R$ ${seguro.toFixed(2).replace(".", ",")}`;
}

function obterResumoConfirmacao() {
    const bruto = carrinho.reduce((total, item) => total + (item.preco * item.quantidade), 0);
    const associado = clienteSelect?.options[clienteSelect.selectedIndex]?.dataset.associado === 'true';
    const desconto = associado ? bruto * (descontoAssociado / 100) : 0;
    const liquido = Math.round((bruto - desconto) * 100) / 100;
    return {
        subtotal: Math.round(bruto * 100) / 100,
        desconto: Math.round(desconto * 100) / 100,
        total: liquido,
    };
}

function obterMetodosConfirmacao() {
    const metodos = [];
    const forma1 = document.getElementById("forma_pagamento_1")?.value;
    const valor1 = parseFloat(document.getElementById("valor_pagamento_1")?.value || "0") || 0;
    const forma2 = document.getElementById("forma_pagamento_2")?.value;
    const valor2 = parseFloat(document.getElementById("valor_pagamento_2")?.value || "0") || 0;

    if (forma1 && valor1 > 0) metodos.push({ forma: forma1, valor: valor1 });
    if (forma2 && valor2 > 0) metodos.push({ forma: forma2, valor: valor2 });

    if (metodos.length === 0) {
        const formaUnica = document.getElementById("forma_pagamento")?.value;
        const valorUnico = document.getElementById("valor_recebido")?.value;
        if (formaUnica) {
            metodos.push({
                forma: formaUnica,
                valor: parseFloat(valorUnico || "0") || obterResumoConfirmacao().total,
            });
        }
    }

    return metodos;
}

function atualizarConteudoConfirmacao() {
    const resumo = obterResumoConfirmacao();
    const totalEl = document.getElementById("confirmacao-total");
    const subtotalEl = document.getElementById("confirmacao-subtotal");
    const descontoEl = document.getElementById("confirmacao-desconto");
    const listaEl = document.getElementById("confirmacao-metodos");

    if (totalEl) totalEl.textContent = formatarMoeda(resumo.total);
    if (subtotalEl) subtotalEl.textContent = formatarMoeda(resumo.subtotal);
    if (descontoEl) descontoEl.textContent = formatarMoeda(resumo.desconto);

    if (!listaEl) return;
    const metodos = obterMetodosConfirmacao();

    if (metodos.length === 0) {
        listaEl.innerHTML = '<div class="confirmacao-metodo"><span>Forma não selecionada</span><strong>Selecione acima</strong></div>';
        return;
    }

    listaEl.innerHTML = metodos.map((metodo) => `
        <div class="confirmacao-metodo">
            <span>${formatarMetodoPagamento(metodo.forma)}</span>
            <strong>${formatarMoeda(metodo.valor)}</strong>
        </div>
    `).join("");
}

function abrirConfirmacaoPagamento() {
    if (carrinho.length === 0) {
        mostrarAlerta('Carrinho vazio! Adicione produtos.', 'warning');
        return;
    }

    if (!chaveIdempotenciaVenda) chaveIdempotenciaVenda = criarChaveIdempotencia();

    atualizarConteudoConfirmacao();
    const metodos = obterMetodosConfirmacao();
    const botaoConfirmar = document.getElementById("btn-confirmar-pagamento-modal");
    const areaPagamentoAdmin = document.getElementById("area-pagamento-admin");
    if (botaoConfirmar) {
        botaoConfirmar.disabled = Boolean(areaPagamentoAdmin) && metodos.length === 0;
    }

    const modal = document.getElementById("modal-confirmacao-pagamento");
    if (!modal) return;
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");

    if (window.EasyStoreLoading) window.EasyStoreLoading.forceEnd();
    document.body.classList.add("modal-confirmacao-aberto");
}

function fecharConfirmacaoPagamento() {
    if (confirmacaoVendaEmAndamento) return;
    const modal = document.getElementById("modal-confirmacao-pagamento");
    if (!modal) return;
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-confirmacao-aberto");
    estadoPagamentoPDV = 'idle';
}

function criarChaveIdempotencia() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
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
    formData.set('chave_idempotencia', chaveIdempotenciaVenda);

    const metodos = obterMetodosConfirmacao();
    const usaPix = metodos.some((metodo) => metodo.forma === 'pix');
    formData.set('pix_confirmado', usaPix && pixConfirmadoVenda ? 'true' : 'false');

    const btn = formFinalizar.querySelector('button[type="submit"]');
    if (btn) {
        if (btn.disabled) return;
        btn.disabled = true;
        btn.dataset.originalHtml = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processando venda...';
    }

    const loadingId = window.EasyStoreLoading
        ? window.EasyStoreLoading.begin({ context: "sync", blocking: true, showNow: true })
        : null;

    try {
        const response = await fetch(formFinalizar.action, {
            method: "POST",
            body: formData,
            credentials: "same-origin",
            redirect: "follow",
        });

        if (!response.ok) throw new Error('Falha ao processar venda');

        const respostaUrl = new URL(response.url, window.location.href);
        if (!respostaUrl.pathname.includes('/pdv/venda/')) {
            const erro = respostaUrl.searchParams.get('erro');
            throw new Error(erro ? `Pagamento não concluído: ${erro}` : 'Pagamento não concluído');
        }

        estadoPagamentoPDV = 'success';
        carrinho = [];
        limparCarrinhoPersistidoPDV();
        window.location.href = response.url;
    } catch (error) {
        mostrarAlerta("Erro ao finalizar venda. Verifique sua conexão e tente novamente.", "warning");
        estadoPagamentoPDV = 'error';
        if (btn) {
            btn.disabled = false;
            if (btn.dataset.originalHtml) btn.innerHTML = btn.dataset.originalHtml;
        }
    } finally {
        if (loadingId && window.EasyStoreLoading) {
            window.EasyStoreLoading.end(loadingId);
        }
    }
}

const PDV_CART_STORAGE_KEY = 'easystore.pdv.carrinho.v1';

function salvarCarrinhoPDV() {
    try {
        sessionStorage.setItem(PDV_CART_STORAGE_KEY, JSON.stringify(carrinho));
    } catch (error) {
        console.warn('Não foi possível preservar o carrinho no navegador.', error);
    }
}

function restaurarCarrinhoPDV() {
    try {
        const salvo = sessionStorage.getItem(PDV_CART_STORAGE_KEY);
        if (!salvo) return;
        const itens = JSON.parse(salvo);
        if (!Array.isArray(itens)) return;

        carrinho = itens.filter((item) =>
            item &&
            Number.isInteger(Number(item.produto_id)) &&
            Number(item.quantidade) > 0
        ).map((item) => ({
            chave: String(item.chave || item.produto_id),
            produto_id: Number(item.produto_id),
            variacao_id: item.variacao_id == null ? null : Number(item.variacao_id),
            nome: String(item.nome || 'Produto'),
            preco: Number(item.preco) || 0,
            estoque: Number(item.estoque) || 0,
            quantidade: Number(item.quantidade) || 1,
        }));
    } catch (error) {
        console.warn('Não foi possível restaurar o carrinho salvo.', error);
        sessionStorage.removeItem(PDV_CART_STORAGE_KEY);
    }
}

function limparCarrinhoPersistidoPDV() {
    try {
        sessionStorage.removeItem(PDV_CART_STORAGE_KEY);
    } catch (error) {
        console.warn('Não foi possível limpar o carrinho persistido.', error);
    }
}
