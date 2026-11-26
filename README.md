# Catálogo de Apps

Cadastro dos seus aplicativos, com banco de dados (SQLite) e o código de cada app guardado dentro do sistema, no estilo do GitHub.

## Quem pode o quê
| | Admin (`domruan1402@gmail.com`) | Outros e-mails cadastrados |
|---|---|---|
| Ver apps, README, código, versões | sim | sim |
| Baixar código (.zip ou arquivo) | sim | sim |
| Criar / editar / excluir apps | sim | não |
| Enviar / excluir versões de código | sim | não |
| Ver e remover usuários | sim | não |

As permissões são checadas **no servidor**, não só escondidas na tela.
O e-mail do admin não pode ser cadastrado pela tela "Criar conta": a conta dele é criada na primeira execução.

## Rodar no seu computador
```bash
pip install -r requirements.txt
python app.py --seed      # --seed cadastra 13 apps de exemplo (só na 1ª vez; pode omitir)
```
Abra http://127.0.0.1:8000

Na primeira execução o sistema gera a senha do admin, mostra no terminal e salva em `data/senha_admin_inicial.txt`.
Entre com `domruan1402@gmail.com`, clique em **Alterar senha** e apague esse arquivo.
Para escolher a senha antes: `ADMIN_PASSWORD=suaSenhaForte python app.py`.

## Publicar online de graça (servidor grátis + banco no Neon)
O banco fica no **Neon** (Postgres grátis, permanente). O servidor pode ser qualquer um gratuito (Render grátis, etc.): ele pode dormir e reiniciar sem perder dados.

1. No Neon, copie a URL de conexão (`postgresql://...`). Ela contém a senha: nunca coloque no GitHub.
2. No servidor, defina as variáveis de ambiente:
   - `DATABASE_URL` = a URL do Neon
   - `ADMIN_PASSWORD` = a senha que você quer para `domruan1402@gmail.com`
   - `REQUIRE_DATABASE_URL=1`, `COOKIE_SECURE=1`, `BEHIND_PROXY=1`
   - `SEED_ON_START=1` (só na primeira vez; cadastra os 13 apps de exemplo)
3. Comando de início: `gunicorn -w 2 -b 0.0.0.0:$PORT app:app`
4. Sem `DATABASE_URL` o sistema usa SQLite local (bom para testar no seu computador, mas os dados somem em hospedagens sem disco).

Há também `Dockerfile` e `Procfile` prontos.

## API (para outras ferramentas)
Todas as chamadas exigem login por cookie e o cabeçalho `X-Requested-With: catalogo`. Escrita só para o admin.
`POST /api/login` · `GET /api/apps` · `POST /api/apps` · `GET/PUT/DELETE /api/apps/<slug>` · `POST /api/apps/<slug>/versions` (multipart: tag, notes, files[], paths[]) · `GET /api/versions/<id>/files` · `GET /api/versions/<id>/download`. Teste de saúde: `GET /healthz`.

## Variáveis de ambiente
`ADMIN_EMAIL` (padrão domruan1402@gmail.com) · `ADMIN_PASSWORD` · `DATA_DIR` · `HOST` · `PORT` · `COOKIE_SECURE` · `BEHIND_PROXY`

## Limites
5 MB por arquivo · 50 MB por versão · 1000 arquivos por versão. Pastas `.git`, `node_modules`, `venv` são ignoradas no envio.

## Estrutura
```
app.py          servidor + banco + regras de acesso
static/         telas (index.html, app.js, style.css)
data/           criado ao rodar: catalogo.db, secret.key
```

## API para o Claude cadastrar apps (`/api/publish`)

Defina a variável `API_TOKEN` no servidor. Depois:

```
POST /api/publish          Authorization: Bearer <API_TOKEN>
{ "name": "...", "description": "...", "category": "...", "tech": ["HTML","JS"],
  "url": "", "readme": "# ...", "version": "1.0", "notes": "...",
  "files": [ {"path": "index.html", "content": "..."}, {"path": "img.png", "content_b64": "..."} ] }
GET  /api/publish/apps     lista os apps (para checar duplicados)
```

O status é sempre `pronto`. Se o nome já existir, o app é atualizado e a versão é substituída (mesmo `version`) ou criada.
