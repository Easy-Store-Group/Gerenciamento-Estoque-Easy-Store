# Implementação de Variações (Cores e Tamanhos)

## O que foi implementado

Este sistema permite que produtos tenham variações (combinações de cores e tamanhos) que podem ser selecionadas:
- **Admin**: Pode cadastrar cores, tamanhos e criar variações para cada produto
- **Cliente**: Pode escolher a cor e tamanho ao reservar um produto
- **PDV**: Admin pode selecionar a cor/tamanho ao fazer uma venda

## Arquivos criados/modificados

### Modelos (Models)
- **`app/models/cor_tamanho.py`** - Novo arquivo com modelos `Cor` e `Tamanho`
- **`app/models/variacao.py`** - Atualizado para incluir relacionamentos com cores e tamanhos
- **`app/models/produto.py`** - Adicionado relacionamento com variações

### Controllers
- **`app/controllers/variacao_controller.py`** - Completely refactored com endpoints para:
  - Gerenciar cores (GET, POST, PUT, DELETE)
  - Gerenciar tamanhos (GET, POST, PUT, DELETE)
  - Gerenciar variações (GET, POST, PUT, DELETE, entrada/saída de estoque)

### Templates HTML
- **`app/templates/admin/variacoes.html`** - NOVO - Admin pode cadastrar cores, tamanhos e variações
- **`app/templates/produtos_publicos.html`** - Atualizado com JavaScript para carregar variações dinamicamente
- **`app/templates/admin/pos.html`** - Atualizado com modal para seleção de variações no PDV

### JavaScript
- **`app/static/js/pdv.js`** - Atualizado para suportar seleção de variações

## Como executar a migration

### 1. Criar a migration

```bash
# No diretório raiz do projeto
alembic revision --autogenerate -m "adicionar_cores_tamanhos_variacoes"
```

### 2. Revisar o arquivo de migration gerado

Verifique o arquivo criado em `migrations/versions/` para garantir que está correto.

### 3. Executar a migration

```bash
alembic upgrade head
```

## Estrutura do Banco de Dados

### Tabelas criadas:
- **cores**: id, nome, codigo_hex, ativa
- **tamanhos**: id, nome, ativa

### Tabela modificada:
- **produto_variacoes**: 
  - Removeu coluna `tamanho` (string)
  - Adicionou `cor_id` (FK cores)
  - Adicionou `tamanho_id` (FK tamanhos)
  - Constraint única: (produto_id, cor_id, tamanho_id)

## Endpoints da API

### Cores
- `GET /api/cores` - Lista todas as cores ativas
- `POST /api/cores` - Cria nova cor
- `PUT /api/cores/{cor_id}` - Atualiza cor
- `DELETE /api/cores/{cor_id}` - Inativa cor

### Tamanhos
- `GET /api/tamanhos` - Lista todos os tamanhos ativos
- `POST /api/tamanhos` - Cria novo tamanho
- `PUT /api/tamanhos/{tamanho_id}` - Atualiza tamanho
- `DELETE /api/tamanhos/{tamanho_id}` - Inativa tamanho

### Variações
- `GET /api/variacoes/produto/{produto_id}` - Lista variações de um produto
- `GET /api/variacoes/{variacao_id}` - Detalhe de uma variação
- `POST /api/variacoes` - Cria nova variação
- `PUT /api/variacoes/{variacao_id}` - Atualiza variação
- `PUT /api/variacoes/{variacao_id}/entrada` - Adiciona estoque
- `PUT /api/variacoes/{variacao_id}/saida` - Remove estoque
- `DELETE /api/variacoes/{variacao_id}` - Deleta variação

## Como usar

### 1. Admin cadastra cores e tamanhos

Acesse `/admin` e clique em "Variações" no menu. Primeira aba "Cores", segunda "Tamanhos".

### 2. Admin cria variações para produtos

Na terceira aba "Variações", selecione o produto e crie combinações de cor/tamanho com estoque inicial.

### 3. Cliente escolhe variações

Na página de produtos públicos (`/auth/produtos`), ao clicar num produto, os selects de cor/tamanho são preenchidos dinamicamente.

### 4. PDV seleciona variação

No PDV, ao clicar num produto, se houver variações, um modal pede para selecionar cor/tamanho antes de adicionar ao carrinho.

## Notas importantes

- Variações são opcionais - produtos sem cores/tamanhos funcionam normalmente
- O estoque do produto é calculado pela soma de todas as variações
- Cores podem ter código hex para exibição visual
- A constraint única garante que não haja duplicação de combinações

## Próximos passos (opcional)

- Adicionar imagens específicas por variação
- Adicionar filtros por variação na listagem de produtos
- Integrar com um sistema de inventário mais avançado
