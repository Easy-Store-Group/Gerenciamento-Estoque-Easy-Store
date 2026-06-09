# 🎮 EasyStore PDV

> Sistema completo de Ponto de Venda para loja de games com sistema inovador de XP e fidelidade gamificada.

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?style=flat&logo=chartdotjs&logoColor=white)

---

## ✨ Funcionalidades

### 🛒 Frente de Caixa (PDV)
- Busca em tempo real de produtos por nome ou categoria
- Suporte a múltiplas formas de pagamento
- Cancelamento de itens ou venda completa
- Interface responsiva e moderna

### 🎮 Sistema de XP e Fidelidade
- **1 Real = 1 XP** acumulado automaticamente
- **10 níveis** de progressão com bonificações
- Conquistas e descontos automáticos ao atingir marcos

### 📊 Dashboard de Caixa
- Resumo do dia e gráficos de fluxo
- Análise por categoria e produtos mais vendidos
- Alertas de estoque baixo

### 📦 Gestão de Estoque
- Cadastro com categorias e estoque mínimo
- Rastreamento automático de movimentações

### 👤 Perfil do Cliente
- XP acumulado, nível atual e conquistas desbloqueadas
- Visualização das próximas recompensas

---

## 🚀 Como Rodar

```bash
# Instalar dependências
pip install -r requirements.txt

# Popular o banco de dados
python seed_db.py

# Iniciar o servidor
uvicorn app.main:app --reload
```

### URLs Principais

| Tela | URL |
|---|---|
| PDV | http://localhost:8000/admin/pos |
| Dashboard | http://localhost:8000/admin/caixa |
| Perfil do cliente | http://localhost:8000/perfil?id=1 |

---

## 🛠️ Endpoints da API

| Rota | Descrição |
|---|---|
| `/api/vendas/` | Vendas e operações de caixa |
| `/api/caixa/` | Dashboard e analytics |
| `/api/conquistas/` | Sistema de achievements |

---

## 🧱 Tecnologias

- **FastAPI** — backend e roteamento
- **SQLAlchemy** — ORM e modelos
- **SQLite** — banco de dados local
- **Jinja2** — templates HTML
- **Chart.js** — gráficos no dashboard
- **Vanilla JS + CSS** — frontend responsivo