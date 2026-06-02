let cart = [];
let allProducts = [];
let selectedPaymentMethod = null;
let currentCustomer = null;

// Carrega os produtos assim que a tela abre
document.addEventListener("DOMContentLoaded", () => {
    loadProducts();
});

async function loadProducts() {
  try {
    const response = await fetch('/api/vendas/produtos');
    allProducts = await response.json();
    renderProducts(allProducts);
  } catch (error) {
    console.error('Erro ao carregar produtos:', error);
    // Fallback visual caso a rota da API demore ou falhe
    document.getElementById('productsGrid').innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #64748b;">Erro ao carregar catálogo de produtos.</div>';
  }
}

function renderProducts(products) {
  const grid = document.getElementById('productsGrid');

  if (products.length === 0) {
    grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #64748b;">Nenhum produto encontrado</div>';
    return;
  }

  grid.innerHTML = products.map(p => `
    <div class="product-card" onclick="addToCart(${p.id}, '${p.nome}', ${p.preco})">
      <img src="${p.imagem}" alt="${p.nome}" class="product-image" onerror="this.src='/static/img/produto-placeholder.png'">
      <div class="product-category">${p.categoria}</div>
      <div class="product-name">${p.nome}</div>
      <div class="product-price">R$ ${p.preco.toFixed(2).replace('.', ',')}</div>
      <div class="product-stock">
        ${p.estoque > 0 ? `Estoque: ${p.estoque}` : '<span style="color: #ef4444;">Fora de estoque</span>'}
      </div>
      <button class="btn-add">+ Adicionar</button>
    </div>
  `).join('');
}

function addToCart(productId, name, price) {
  const existing = cart.find(item => item.productId === productId);

  if (existing) {
    existing.quantity++;
  } else {
    cart.push({ productId, name, price, quantity: 1 });
  }

  updateCart();
}

function updateCart() {
  const cartContainer = document.getElementById('cartItems');

  if (cart.length === 0) {
    cartContainer.innerHTML = '<div class="cart-empty">Nenhum produto selecionado</div>';
    document.getElementById('cartItemCount').textContent = '0 itens';
    document.getElementById('checkoutBtn').disabled = true;
    updateTotals();
    return;
  }

  cartContainer.innerHTML = cart.map((item, index) => `
    <div class="cart-item">
      <div class="cart-item-name">
        ${item.name} 
        <button class="cart-item-remove" onclick="event.stopPropagation(); removeFromCart(${index})">✕</button>
      </div>
      <div class="cart-item-qty">Qtd:
        <input type="number" min="1" value="${item.quantity}" onchange="updateQuantity(${index}, this.value)" onclick="event.stopPropagation();" style="width: 50px; padding: 4px; border: 1px solid #e2e8f0; border-radius: 6px; text-align: center;">
      </div>
      <div class="cart-item-price">R$ ${(item.price * item.quantity).toFixed(2).replace('.', ',')}</div>
    </div>
  `).join('');

  document.getElementById('cartItemCount').textContent = `${cart.length} item(ns)`;
  document.getElementById('checkoutBtn').disabled = false;
  updateTotals();
}

function updateQuantity(index, value) {
  const qty = parseInt(value) || 1;
  if (qty > 0) {
    cart[index].quantity = qty;
  } else {
    cart.splice(index, 1);
  }
  updateCart();
}

function removeFromCart(index) {
  cart.splice(index, 1);
  updateCart();
}

function updateTotals() {
  const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  const subtotalFormatado = `R$ ${subtotal.toFixed(2).replace('.', ',')}`;

  document.getElementById('subtotal').textContent = subtotalFormatado;
  document.getElementById('total').textContent = subtotalFormatado;
  document.getElementById('discountRow').style.display = 'none';
}

// Busca de cliente por email
document.getElementById('customerEmail').addEventListener('change', async (e) => {
  const email = e.target.value.trim();
  if (!email) {
    currentCustomer = null;
    document.getElementById('customerInfo').style.display = 'none';
    return;
  }

  try {
    const response = await fetch(`/api/vendas/usuario-por-email?email=${encodeURIComponent(email)}`);
    if (response.ok) {
      const usuario = await response.json();
      currentCustomer = usuario;
      document.getElementById('customerName').textContent = usuario.nome;
      document.getElementById('customerLevel').textContent = usuario.nivel;
      document.getElementById('customerXP').textContent = usuario.xp_total;
      document.getElementById('customerInfo').style.display = 'block';
    } else {
      document.getElementById('customerInfo').style.display = 'none';
    }
  } catch (error) {
    console.error('Erro ao buscar cliente:', error);
  }
});

// Filtro de Busca Dinâmica
document.getElementById('searchProducts').addEventListener('input', (e) => {
  const query = e.target.value.toLowerCase();
  const filtered = allProducts.filter(p =>
    p.nome.toLowerCase().includes(query) ||
    p.categoria.toLowerCase().includes(query)
  );
  renderProducts(filtered);
});

// Abrir e fechar Modal de Confirmação
document.getElementById('checkoutBtn').addEventListener('click', () => {
  if (!currentCustomer && !document.getElementById('customerEmail').value) {
    alert('Informe o email do cliente antes de prosseguir.');
    return;
  }
  document.getElementById('paymentModal').classList.add('active');
});

function closePaymentModal() {
  document.getElementById('paymentModal').classList.remove('active');
}

document.querySelectorAll('.payment-btn').forEach(btn => {
  btn.addEventListener('click', (e) => {
    document.querySelectorAll('.payment-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    selectedPaymentMethod = e.target.dataset.method;
  });
});

// Envio final para API de Vendas
document.getElementById('confirmPaymentBtn').addEventListener('click', async () => {
  if (!selectedPaymentMethod) {
    alert('Selecione uma forma de pagamento');
    return;
  }

  const itens = cart.map(item => ({
    produto_id: item.productId,
    quantidade: item.quantity
  }));

  try {
    const response = await fetch('/api/vendas/finalizar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        itens,
        metodos_pagamento: selectedPaymentMethod,
        usuario_email: document.getElementById('customerEmail').value || null
      })
    });

    const resultado = await response.json();

    if (response.ok) {
      closePaymentModal();
      if(typeof showXpNotification === 'function') showXpNotification(resultado.xp_ganho);

      if (resultado.conquista && typeof showAchievementPopup === 'function') {
        showAchievementPopup(resultado.conquista.nome, `+R$ ${resultado.conquista.desconto} de desconto`);
      }
      
      // Reseta o estado do PDV após sucesso
      cart = [];
      selectedPaymentMethod = null;
      document.querySelectorAll('.payment-btn').forEach(b => b.classList.remove('active'));
      updateCart();
      alert('Venda processada com sucesso!');
    } else {
      alert('Erro ao finalizar venda: ' + resultado.error);
    }
  } catch (error) {
    console.error('Erro na requisição de fechamento:', error);
  }
});