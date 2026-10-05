# X Replies MCP

MCP pequeno para ler um post público do X e buscar replies recentes usando **Application Bearer Token** (app-only), sem OAuth de usuário.

## Ferramentas

- `get_post(url_or_id)` — lê o post original.
- `get_replies(url_or_id, limit=100, direct_only=false, include_authors=true)` — busca até 200 replies recentes da conversa.

> Observação: o endpoint Recent Search do X só cobre a janela recente disponível para sua conta/API. O custo da API do X continua sendo cobrado normalmente no seu projeto.

## Deploy no Render — jeito mais fácil

1. Crie um repositório GitHub novo e envie estes arquivos.
2. No Render, escolha **New > Blueprint** e selecione o repositório. O `render.yaml` configura o serviço.
3. Quando o Render pedir a variável `X_BEARER_TOKEN`, cole seu Bearer Token atual do X.
4. Faça o deploy.
5. Sua URL MCP será:

   `https://SEU-SERVICO.onrender.com/mcp`

6. Cadastre essa URL como Custom MCP no Composio ou no host MCP que você usar.

## Teste local opcional

```bash
pip install -r requirements.txt
set X_BEARER_TOKEN=SEU_TOKEN
uvicorn server:app --host 127.0.0.1 --port 8000
```

Endpoint local:

`http://127.0.0.1:8000/mcp`

## Uso desejado no ChatGPT

Depois que o MCP estiver conectado, você pode pedir algo como:

> Analise as respostas deste post: https://x.com/usuario/status/123...

O modelo pode chamar `get_post` e depois `get_replies` automaticamente.

## Segurança

- Nunca coloque o Bearer Token dentro do código ou em um repositório público.
- Use sempre a variável secreta `X_BEARER_TOKEN` do Render.
- Se um token aparecer em print/chat/arquivo compartilhado, regenere-o no X Developer.
