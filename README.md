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

## Publicar online (link único) — passo a passo no Render
1. Crie uma conta em https://github.com e um repositório **privado** novo (ex.: `catalogo-de-apps`). Envie todos os arquivos desta pasta para ele (botão *Add file → Upload files*).
2. Crie uma conta em https://render.com e clique em **New → Blueprint**. Conecte o GitHub e escolha o repositório: o Render lê o `render.yaml` sozinho.
3. Quando ele pedir `ADMIN_PASSWORD`, digite a senha que você quer para `domruan1402@gmail.com`.
4. Clique em **Apply**. Em alguns minutos aparece o link, algo como `https://catalogo-de-apps.onrender.com`. Esse é o link único para você e para os outros.
5. Abra o link, entre com seu e-mail e a senha. Os 13 apps de exemplo já vêm cadastrados (`SEED_ON_START=1`; depois pode apagar essa variável).

Observações:
- O plano **starter** (pago, cerca de US$ 7/mês) é necessário para ter o **disco persistente** onde fica o banco. Sem disco, os dados se perdem a cada reinício.
- Alternativas: Railway, Fly.io ou um VPS. Há um `Dockerfile` pronto (`docker build -t catalogo .` e `docker run -p 8000:8000 -v dados:/data -e ADMIN_PASSWORD=suaSenha catalogo`).
- HTTPS já vem ligado no Render; mantenha `COOKIE_SECURE=1`.
- Faça backup do arquivo `catalogo.db` (apps, usuários e todo o código ficam nele).

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
