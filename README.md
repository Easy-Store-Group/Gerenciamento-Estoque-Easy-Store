# 🎮 EasyStore - PDV com Sistema XP Gamificado

Sistema completo de Ponto de Venda (PDV) para loja de games com sistema inovador de XP e fidelidade gamificada.

## ✨ Funcionalidades

### 🛒 Frente de Caixa (PDV)
- **Busca Rápida**: Busca em tempo real de produtos por nome ou categoria
- **Multi-Pagamento**: Suporte para múltiplas formas de pagamento
- **Cancelamento**: Remover itens ou cancelar venda completa
- **Interface Responsiva**: Design moderno otimizado

### 🎮 Sistema de XP e Fidelidade
- **1 Real = 1 XP**: Acúmulo automático
- **10 Níveis**: Progressão com bonificações
- **Conquistas**: Descontos automáticos ao atingir marcos

### 📊 Dashboard de Caixa
- Resumo do dia, gráficos de fluxo, análise por categoria
- Produtos mais vendidos, alertas de estoque

### 📦 Gestão de Estoque
- Cadastro com categorias, estoque mínimo, rastreamento automático

### 👤 Perfil do Cliente
- XP, nível, conquistas desbloqueadas, próximas recompensas

## 🚀 Como Usar

```bash
# Instalar e rodar
pip install -r requirements.txt
python seed_db.py
uvicorn app.main:app --reload
```

**URLs principais:**
- PDV: http://localhost:8000/admin/pos
- Dashboard: http://localhost:8000/admin/caixa
- Perfil: http://localhost:8000/perfil?id=1

## 🛠️ APIs

- `/api/vendas/` - Vendas e operações
- `/api/caixa/` - Dashboard e analytics
- `/api/conquistas/` - Sistema de achievements

## ✅ Desenvolvido com

- FastAPI + SQLAlchemy
- Responsive CSS + JavaScript vanilla
- Chart.js para gráficos
- SQLite para banco de dados
