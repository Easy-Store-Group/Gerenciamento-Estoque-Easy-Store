let carrinho = [];

function adicionarAoCarrinho(nome, preco) {
    carrinho.push({ nome, preco });
    atualizarInterface();
}

function atualizarInterface() {
    const lista = document.getElementById('lista-carrinho');
    const totalElemento = document.getElementById('total-venda');
    
    if (carrinho.length === 0) {
        lista.innerHTML = '<p class="sub-placeholder">Caixa Livre</p>';
    } else {
        lista.innerHTML = carrinho.map(item => `
            <div class="cart-row">
                <span class="col-item">${item.nome}</span>
                <span class="col-qtd">1</span>
                <span class="col-total">R$ ${item.preco.toFixed(2)}</span>
            </div>
        `).join('');
    }

    const total = carrinho.reduce((sum, item) => sum + item.preco, 0);
    totalElemento.innerText = `R$ ${total.toLocaleString('pt-br', {minimumFractionDigits: 2})}`;
}

function limparCarrinho() {
    carrinho = [];
    atualizarInterface();




    function atualizarInterface() {
    const lista = document.getElementById('lista-carrinho');
    const totalElemento = document.getElementById('total-venda');
    
    if (carrinho.length === 0) {
        lista.innerHTML = '<p style="text-align:center; margin-top:50px; color:#999;">Caixa Livre</p>';
    } else {
        // Renderiza cada item respeitando as colunas de classe
        lista.innerHTML = carrinho.map(item => `
            <div class="cart-row">
                <span class="col-item">${item.nome}</span>
                <span class="col-qtd">1</span>
                <span class="col-total">R$ ${item.preco.toFixed(2)}</span>
            </div>
        `).join('');
    }

    const total = carrinho.reduce((sum, item) => sum + item.preco, 0);
    totalElemento.innerText = `R$ ${total.toLocaleString('pt-br', {minimumFractionDigits: 2})}`;
function adicionarAoCarrinho(nome, preco, fotoUrl)

{
    carrinho.push({ nome, preco, fotoUrl }); // Agora guardamos a foto também
    atualizarInterface();
}

function atualizarInterface() {
    const lista = document.getElementById('lista-carrinho');
    // ... parte do código anterior ...
    lista.innerHTML = carrinho.map(item => `
        <div class="cart-row">
            <span class="col-item" style="display:flex; align-items:center; gap:10px;">
                <img src="${item.fotoUrl}" style="width:30px; height:30px; border-radius:4px; object-fit:cover;">
                ${item.nome}
            </span>
            <span class="col-qtd">1</span>
            <span class="col-total">R$ ${item.preco.toFixed(2)}</span>
        </div>
    `).join('');
    // ... resto da função ...
}


}
}