# 🧪 Guia de Testes - EasyStore PDV

## Teste 1: Frente de Caixa Básica

1. Acesse: `http://localhost:8000/admin/pos`
2. Na busca, digite "PlayStation"
3. Clique em "+ Adicionar" na PlayStation 5
4. Veja o carrinho aparecer com R$ 3.999,90
5. Clique em "Finalizar Venda"
6. Selecione "PIX" como forma de pagamento
7. Confirme - você verá a notificação de +3999 XP ganho

**Resultado Esperado**: Venda finalizada com sucesso, carrinho limpo, notificação de XP

## Teste 2: Multi-Pagamento

1. No PDV, adicione:
   - PlayStation 5: R$ 3.999,90
   - DualSense: R$ 450,00
   - Total: R$ 4.449,90

2. Finalizar venda → Multi-pagamento: "Dinheiro 2000, PIX 2449.90"
3. Confirmar

**Resultado Esperado**: Venda aceita com múltiplos pagamentos

## Teste 3: Sistema de XP e Conquistas

1. Primeiro, visualize o Dashboard: `http://localhost:8000/admin/caixa`
2. Veja o "Resumo do Dia" com vendas já realizadas
3. Acesse Perfil: `http://localhost:8000/perfil?id=1`
4. Você verá:
   - XP Total (soma de todas as vendas)
   - Nível (calculado baseado em XP)
   - Conquistas desbloqueadas (badges com ícones)
   - Próxima conquista (barra de progresso)

**Resultado Esperado**: Perfil mostra progressão de XP e conquistas

## Teste 4: Alertas de Estoque

1. Dashboard: `http://localhost:8000/admin/caixa`
2. Veja a seção "⚠️ Alertas de Estoque"
3. Produtos com estoque crítico (vermelho)
4. Produtos com estoque baixo (amarelo)

**Resultado Esperado**: Alertas aparecem apenas para produtos com estoque <= estoque_minimo

## Teste 5: Cancelamento de Venda

**Nota:** Funcionalidade para admin/gerente

1. Venda algo normalmente
2. Via API ou admin, use:
   ```
   DELETE /api/vendas/cancelar/{venda_id}
   ```
3. Estoque é restaurado
4. XP é removido do cliente

## Teste 6: Busca de Produtos

1. PDV → busca por "controle"
2. Digite "dual" na busca
3. Veja aparecer apenas produtos relevantes
4. Busca funciona em tempo real (sem reload)

## Teste 7: Responsividade

1. Abra o PDV em diferentes tamanhos:
   - Desktop (1920px) - layout com grid
   - Tablet (768px) - grid ajusta
   - Mobile (375px) - coluna única

2. Toque funciona em todos os botões

## APIs para Testar

### Buscar Produtos
```bash
curl http://localhost:8000/api/vendas/produtos
curl http://localhost:8000/api/vendas/produtos/busca?q=playstation
```

### Finalizar Venda
```bash
curl -X POST http://localhost:8000/api/vendas/finalizar \
  -H "Content-Type: application/json" \
  -d '{
    "itens": [{"produto_id": 1, "quantidade": 1}],
    "metodos_pagamento": "PIX",
    "usuario_id": 1
  }'
```

### Dashboard
```bash
curl http://localhost:8000/api/caixa/resumo/dia
curl http://localhost:8000/api/caixa/alertas/estoque
curl http://localhost:8000/api/caixa/top-produtos
```

### Conquistas
```bash
curl http://localhost:8000/api/conquistas/
curl http://localhost:8000/api/conquistas/usuario/1
```

## Dados de Teste Padrão

Usuários criados pelo `seed_db.py`:
- Admin: admin@easystore.com (role: admin)
- Vendedor: vendedor@easystore.com (role: operador)
- Cliente: joao@example.com (role: cliente)

Todos com senha: `password123`

Produtos:
- PlayStation 5: R$ 3.999,90 (Estoque: 5)
- Xbox Series X: R$ 4.499,90 (Estoque: 3)
- Elden Ring: R$ 299,90 (Estoque: 15)
- DualSense: R$ 450,00 (Estoque: 20)
- Fone Corsair: R$ 549,90 (Estoque: 8)
- Funko Pop: R$ 89,90 (Estoque: 12)

Conquistas (pré-carregadas):
- Primeira Compra (50 XP): +R$ 5
- Colecionador (100 XP): +R$ 10
- Gamer Casual (500 XP): +R$ 15
- Gamer Pro (1000 XP): +R$ 20
- Lendário (5000 XP): +R$ 50

## Checklist de Validação

- [ ] PDV carrega sem erros
- [ ] Busca funciona em tempo real
- [ ] Carrinho atualiza corretamente
- [ ] Finalizar venda calcula XP
- [ ] Notificações aparecem
- [ ] Dashboard mostra dados
- [ ] Alertas de estoque aparecem
- [ ] Perfil mostra conquistas
- [ ] Multi-pagamento funciona
- [ ] Cancelamento restaura estoque
- [ ] Layout é responsivo
- [ ] API endpoints retornam dados corretos
