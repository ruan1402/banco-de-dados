"use strict";

const root = document.getElementById("root");
const STATUS = { ideia: "Ideia", desenvolvimento: "Em desenvolvimento", pronto: "Pronto", arquivado: "Arquivado" };
let ME = null;
let navId = 0;

/* ---------- utilidades ---------- */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const fmtDate = (iso) => new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
const fmtSize = (n) => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`;

async function api(method, url, body, isForm) {
  const opts = { method, headers: { "X-Requested-With": "catalogo" }, credentials: "same-origin" };
  if (body !== undefined) {
    if (isForm) opts.body = body;
    else { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  }
  let r;
  try { r = await fetch(url, opts); }
  catch { const e = new Error("Sem conexão com o servidor."); e.status = 0; throw e; }
  let data = null;
  try { data = await r.json(); } catch { /* sem corpo */ }
  if (!r.ok) {
    const e = new Error((data && data.error) || "Algo deu errado.");
    e.status = r.status;
    throw e;
  }
  return data;
}

function toast(msg, isErr) {
  const t = document.createElement("div");
  t.className = "toast" + (isErr ? " err" : "");
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 4500);
}

function modal(html) {
  const dlg = document.createElement("dialog");
  dlg.innerHTML = html;
  document.body.appendChild(dlg);
  dlg.addEventListener("close", () => dlg.remove());
  dlg.showModal();
  return dlg;
}

function confirmBox(msg, okLabel = "Confirmar") {
  return new Promise((resolve) => {
    const dlg = modal(`<p>${esc(msg)}</p>
      <div class="actions"><button class="btn" data-v="0">Cancelar</button>
      <button class="btn danger" data-v="1">${esc(okLabel)}</button></div>`);
    dlg.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-v]");
      if (b) { resolve(b.dataset.v === "1"); dlg.close(); }
    });
    dlg.addEventListener("cancel", () => resolve(false));
  });
}

function go(hash) {
  if (location.hash === hash) route(); else location.hash = hash;
}

/* ---------- estrutura da página ---------- */
function shell(inner) {
  if (!ME) { root.innerHTML = `<main class="auth-screen">${inner}</main>`; return; }
  const h = location.hash;
  const active = h.startsWith("#/novo") ? "novo" : h.startsWith("#/usuarios") ? "usuarios" : "apps";
  const on = (k) => (active === k ? "on" : "");
  root.innerHTML = `
    <div class="page">
      <header class="topbar">
        <nav class="menu" aria-label="Menu principal">
          <a href="#/" class="${on("apps")}">Aplicações</a>
          ${ME.admin ? `<a href="#/novo" class="${on("novo")}">Novo app</a>
          <a href="#/usuarios" class="${on("usuarios")}">Usuários</a>` : ""}
        </nav>
        <div class="account">
          <div class="who"><span>${esc(ME.email)}</span><small>${ME.admin ? "Administrador" : "Somente visualização"}</small></div>
          ${ME.admin ? `<button class="btn ghost" id="btn-sync" title="Buscar projetos novos enviados pelo Claude">Sincronizar</button><button class="btn ghost" id="btn-pw">Senha</button>` : ""}
          <button class="btn ghost" id="btn-logout">Sair</button>
        </div>
      </header>
      <main class="main">${inner}</main>
    </div>`;
  $("#btn-logout").onclick = async () => { try { await api("POST", "/api/logout"); } catch { /* ignora */ } ME = null; go("#/login"); };
  if ($("#btn-pw")) $("#btn-pw").onclick = changePasswordDialog;
  if ($("#btn-sync")) $("#btn-sync").onclick = async () => {
    const b = $("#btn-sync"); b.disabled = true; b.textContent = "Sincronizando…";
    try {
      const { result: r } = await api("POST", "/api/sync");
      const n = r ? (r.novos || []).length + (r.atualizados || []).length : 0;
      if (r && r.erro) toast("Erro: " + r.erro);
      else { toast(n ? `${n} projeto(s) sincronizado(s).` : "Tudo já estava atualizado."); if (n) { navId++; route(); } }
    } catch (e) { toast(e.message); }
    b.disabled = false; b.textContent = "Sincronizar";
  };
}

const head = (eyebrow, title, right = "") =>
  `<header class="head"><div><span class="eyebrow">${esc(eyebrow)}</span><h1>${esc(title)}</h1></div>${right}</header>`;
const initials = (n) => n.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";
const covC = (id) => "c" + (Number(id) % 10);
const denied = () => shell(`<div class="panel aside narrow"><h1>Sem permissão</h1><p class="muted">Apenas o administrador pode fazer isso. Você pode visualizar os apps, READMEs, códigos e versões.</p><a class="btn primary" href="#/">Voltar às aplicações</a></div>`);

function showError(e) {
  shell(`<div class="panel aside narrow"><h2>Ops</h2><p>${esc(e.message)}</p><a class="btn" href="#/">Voltar ao início</a></div>`);
}

function changePasswordDialog() {
  const dlg = modal(`<h3>Alterar senha</h3>
    <form id="f-pw">
      <label for="pw-a">Senha atual</label><input id="pw-a" type="password" autocomplete="current-password" required>
      <label for="pw-n">Nova senha <small>(mínimo 8 caracteres)</small></label>
      <input id="pw-n" type="password" autocomplete="new-password" minlength="8" required>
      <div class="err" id="pw-err"></div>
      <div class="actions"><button type="button" class="btn" id="pw-c">Cancelar</button>
      <button class="btn primary">Salvar</button></div>
    </form>`);
  $("#pw-c", dlg).onclick = () => dlg.close();
  $("#f-pw", dlg).onsubmit = async (ev) => {
    ev.preventDefault();
    try {
      await api("POST", "/api/password", { atual: $("#pw-a", dlg).value, nova: $("#pw-n", dlg).value });
      dlg.close(); toast("Senha alterada.");
    } catch (e) { $("#pw-err", dlg).textContent = e.message; }
  };
}

/* ---------- login (só e-mail; o administrador também informa a senha) ---------- */
function viewLogin() {
  shell(`<div class="login">
    <section class="hero">
      <span class="eyebrow">Catálogo pessoal</span>
      <h1>Todos os seus apps, num só lugar.</h1>
      <p class="muted">Cadastre cada projeto, escreva o README e guarde o código por versão.</p>
      <ul class="feats">
        <li><span class="cover c0">DB</span>Catálogo com banco de dados, sempre à mão.</li>
        <li><span class="cover c5">{ }</span>Código de cada app guardado em versões, com visualizador.</li>
        <li><span class="cover c9">ADM</span>O administrador edita. Os demais e-mails só visualizam.</li>
      </ul>
    </section>
    <section class="formside"><div class="panel aside auth">
      <h2>Entrar</h2>
      <form id="f-auth">
        <label for="au-e">E-mail</label><input id="au-e" type="email" autocomplete="email" placeholder="voce@exemplo.com" required>
        <div id="au-pbox" hidden>
          <label for="au-p">Senha do administrador</label><input id="au-p" type="password" autocomplete="current-password">
        </div>
        <div class="err" id="au-err" role="alert"></div>
        <button class="btn primary big" id="au-b">Entrar</button>
      </form></div></section></div>`);
  $("#f-auth").onsubmit = async (ev) => {
    ev.preventDefault();
    const btn = $("#au-b"); btn.disabled = true; $("#au-err").textContent = "";
    try {
      const r = await api("POST", "/api/login", { email: $("#au-e").value, password: $("#au-p").value });
      if (r.need_password) { $("#au-pbox").hidden = false; $("#au-p").focus(); btn.disabled = false; return; }
      ME = r.user; go("#/");
    } catch (e) { $("#au-err").textContent = e.message; btn.disabled = false; }
  };
  $("#au-e").focus();
}

/* ---------- início: lista de apps ---------- */
async function viewHome() {
  const my = navId;
  const { apps } = await api("GET", "/api/apps");
  if (my !== navId) return;
  const cats = [...new Set(apps.map((a) => a.category).filter(Boolean))].sort();
  const count = (s) => apps.filter((a) => a.status === s).length;
  shell(`
    ${head("Catálogo pessoal", "Meus aplicativos", `<div class="stats">
      <div class="stat"><small>Apps cadastrados</small><b>${apps.length}</b></div>
      <div class="stat"><small>Prontos</small><b>${count("pronto")}</b></div>
      <div class="stat"><small>Em desenvolvimento</small><b>${count("desenvolvimento")}</b></div></div>`)}
    <div class="listhead"><h2>Lista completa</h2>${ME.admin ? '<a class="btn primary" href="#/novo">Novo app</a>' : ""}</div>
    <div class="filters">
      <input id="q" type="search" placeholder="Buscar por nome, descrição ou tecnologia" aria-label="Buscar">
      <select id="fs" aria-label="Status"><option value="">Todos os status</option>
        ${Object.entries(STATUS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select>
      <select id="fc" aria-label="Categoria"><option value="">Todas as categorias</option>
        ${cats.map((c) => `<option>${esc(c)}</option>`).join("")}</select>
    </div>
    <ul class="list" id="list"></ul>`);
  const draw = () => {
    const q = $("#q").value.trim().toLowerCase(), fs = $("#fs").value, fc = $("#fc").value;
    const rows = apps.filter((a) =>
      (!fs || a.status === fs) && (!fc || a.category === fc) &&
      (!q || [a.name, a.description, a.category, a.tech.join(" ")].join(" ").toLowerCase().includes(q)));
    $("#list").innerHTML = rows.length ? rows.map((a) => `
      <li class="row">
        <span class="cover ${covC(a.id)}" aria-hidden="true">${esc(initials(a.name))}</span>
        <div class="info">
          <a class="name" href="#/app/${encodeURIComponent(a.slug)}">${esc(a.name)}</a>
          <span class="desc">${esc(a.description) || "<i>Sem descrição</i>"}</span>
          <div class="meta">${a.category ? `<span>${esc(a.category)}</span>` : ""}${a.tech.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
        </div>
        <div class="side">
          <span class="badge ${a.status}">${STATUS[a.status]}</span>
          <span class="meta">${a.latest ? esc(a.latest) : "sem código"} · ${fmtDate(a.updated_at)}</span>
        </div>
        ${ME.admin ? `<a class="ib" href="#/app/${encodeURIComponent(a.slug)}/editar" aria-label="Editar ${esc(a.name)}">✎</a>` : ""}
      </li>`).join("")
      : `<li class="empty">${apps.length ? "Nenhum app encontrado com esses filtros."
        : ME.admin ? "Nenhum app cadastrado ainda. Clique em “+ Novo app”." : "Nenhum app cadastrado ainda."}</li>`;
  };
  ["input", "change"].forEach((ev) => $$("#q,#fs,#fc").forEach((el) => el.addEventListener(ev, draw)));
  draw();
}

/* ---------- página de um app ---------- */
async function viewApp(slug, tab) {
  const my = navId;
  const { app: a } = await api("GET", `/api/apps/${encodeURIComponent(slug)}`);
  if (my !== navId) return;
  const base = `#/app/${encodeURIComponent(a.slug)}`;
  const tabs = [["readme", "README"], ["codigo", "Código"], ["versoes", `Versões (${a.versions.length})`]];
  if (!tabs.some((t) => t[0] === tab)) tab = "readme";
  shell(`
    ${head(a.category || "App", a.name, `<div class="actions">
        ${a.url ? `<a class="btn primary" href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">Abrir app ↗</a>` : ""}
        ${ME.admin ? `<a class="btn ghost" href="${base}/versao">Nova versão</a>
          <a class="btn ghost" href="${base}/editar">Editar</a>
          <button class="btn ghost danger" id="del">Excluir</button>` : ""}</div>`)}
    <div class="meta line"><span class="badge ${a.status}">${STATUS[a.status]}</span>
      ${a.tech.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
      <span>${esc(a.description)} · Atualizado em ${fmtDate(a.updated_at)}</span><a href="#/" class="muted">← Todos os apps</a></div>
    <section class="panel big-panel">
    <div class="tabs" role="tablist">${tabs.map(([k, l]) => `<button data-t="${k}" class="${k === tab ? "on" : ""}">${esc(l)}</button>`).join("")}</div>
    <div id="tab"></div></section>`);
  $$(".tabs button").forEach((b) => b.onclick = () => go(b.dataset.t === "readme" ? base : `${base}/${b.dataset.t}`));
  const del = $("#del");
  if (del) del.onclick = async () => {
    if (!(await confirmBox(`Excluir “${a.name}” e todo o código enviado? Isso não pode ser desfeito.`, "Excluir"))) return;
    try { await api("DELETE", `/api/apps/${encodeURIComponent(a.slug)}`); toast("App excluído."); go("#/"); }
    catch (e) { toast(e.message, true); }
  };
  const box = $("#tab");
  if (tab === "readme") {
    box.innerHTML = `<div class="panel md">${a.readme_html || '<p class="muted">Este app ainda não tem README.</p>'}</div>`;
  } else if (tab === "versoes") {
    box.innerHTML = a.versions.length ? `<div class="panel">${a.versions.map((v) => `
      <div class="ver"><div><b>${esc(v.tag)}</b> <span class="muted">· ${fmtDate(v.created_at)} · ${v.n_files} arquivos · ${fmtSize(v.total_size)}</span>
        <div>${esc(v.notes) || '<span class="muted">Sem notas.</span>'}</div></div>
        <div class="actions">
          <a class="btn small" href="/api/versions/${v.id}/download">Baixar .zip</a>
          ${ME.admin ? `<button class="btn small ghost danger" data-del="${v.id}" data-tag="${esc(v.tag)}">Excluir</button>` : ""}
        </div></div>`).join("")}</div>`
      : `<div class="panel note">Nenhuma versão enviada ainda.</div>`;
    $$("[data-del]", box).forEach((b) => b.onclick = async () => {
      if (!(await confirmBox(`Excluir a versão ${b.dataset.tag} e seus arquivos?`, "Excluir"))) return;
      try { await api("DELETE", `/api/versions/${b.dataset.del}`); toast("Versão excluída."); route(); }
      catch (e) { toast(e.message, true); }
    });
  } else {
    codeTab(box, a, base);
  }
}

function buildTree(files) {
  const rootNode = { dirs: {}, files: [] };
  for (const f of files) {
    const parts = f.path.split("/");
    let n = rootNode;
    for (let i = 0; i < parts.length - 1; i++) n = (n.dirs[parts[i]] ??= { dirs: {}, files: [] });
    n.files.push({ ...f, name: parts[parts.length - 1] });
  }
  return rootNode;
}

function treeHtml(n, selected, prefix = "") {
  const dirs = Object.keys(n.dirs).sort().map((d) =>
    `<details ${selected.startsWith(prefix + d + "/") ? "open" : ""}><summary>${esc(d)}</summary>${treeHtml(n.dirs[d], selected, prefix + d + "/")}</details>`).join("");
  const files = n.files.sort((x, y) => x.name.localeCompare(y.name)).map((f) =>
    `<button class="file ${f.path === selected ? "sel" : ""}" data-path="${esc(f.path)}" title="${esc(f.path)}">${esc(f.name)}</button>`).join("");
  return `<div class="tree-level">${dirs}${files}</div>`;
}

function codeTab(box, a, base) {
  if (!a.versions.length) {
    box.innerHTML = `<div class="panel note">Nenhum código enviado ainda.
      ${ME.admin ? `<p><a class="btn primary" href="${base}/versao">Enviar primeira versão</a></p>` : ""}</div>`;
    return;
  }
  box.innerHTML = `
    <div class="code-bar">
      <label for="vsel" class="muted">Versão:</label>
      <select id="vsel">${a.versions.map((v) => `<option value="${v.id}">${esc(v.tag)} — ${fmtDate(v.created_at)}</option>`).join("")}</select>
      <a class="btn small" id="vzip" href="#">Baixar tudo (.zip)</a>
    </div>
    <div class="code-layout">
      <div class="panel tree" id="tree"></div>
      <div class="panel" id="viewer"><div class="note">Selecione um arquivo.</div></div>
    </div>`;
  let vid = a.versions[0].id, files = [], selected = "";

  const openFile = async (path) => {
    selected = path;
    $$(".file", box).forEach((b) => b.classList.toggle("sel", b.dataset.path === path));
    const v = $("#viewer");
    try {
      const f = await api("GET", `/api/versions/${vid}/file?path=${encodeURIComponent(path)}`);
      v.innerHTML = `<div class="viewer-head"><span><b>${esc(f.path)}</b> <span class="muted">· ${fmtSize(f.size)}</span></span>
        <a class="btn small" href="/api/versions/${vid}/raw?path=${encodeURIComponent(f.path)}">Baixar arquivo</a></div>
        <div id="vbody"></div>`;
      const body = $("#vbody", v);
      if (f.is_text) {
        let text = f.text;
        if (text.endsWith("\n")) text = text.slice(0, -1);
        const n = text.split("\n").length;
        body.innerHTML = `<div class="codewrap"><pre class="gutter"></pre><pre class="src"></pre></div>` +
          (f.truncated ? '<div class="note">Arquivo grande: mostrando só o começo. Baixe para ver tudo.</div>' : "");
        $(".gutter", body).textContent = Array.from({ length: n }, (_, i) => i + 1).join("\n");
        $(".src", body).textContent = text;
      } else {
        body.innerHTML = '<div class="note">Arquivo binário — não dá para mostrar aqui. Use “Baixar arquivo”.</div>';
      }
    } catch (e) { v.innerHTML = `<div class="note">${esc(e.message)}</div>`; }
  };

  const loadVersion = async () => {
    $("#vzip").href = `/api/versions/${vid}/download`;
    $("#viewer").innerHTML = '<div class="note">Selecione um arquivo.</div>';
    try { files = (await api("GET", `/api/versions/${vid}/files`)).files; }
    catch (e) { $("#tree").innerHTML = `<div class="note">${esc(e.message)}</div>`; return; }
    const pick = files.find((f) => /^readme(\.\w+)?$/i.test(f.path)) || files.find((f) => /^index\.html?$/i.test(f.path)) || files[0];
    selected = pick ? pick.path : "";
    $("#tree").innerHTML = files.length ? treeHtml(buildTree(files), selected) : '<div class="note">Versão sem arquivos.</div>';
    if (pick) openFile(pick.path);
  };

  $("#vsel").onchange = (e) => { vid = Number(e.target.value); loadVersion(); };
  $("#tree").onclick = (e) => { const b = e.target.closest(".file"); if (b) openFile(b.dataset.path); };
  loadVersion();
}

/* ---------- criar / editar app ---------- */
async function viewForm(slug) {
  if (!ME.admin) return denied();
  const my = navId;
  let a = { name: "", description: "", category: "", status: "desenvolvimento", tech: [], url: "", readme: "" };
  if (slug) { a = (await api("GET", `/api/apps/${encodeURIComponent(slug)}`)).app; if (my !== navId) return; }
  shell(`${head("Administração", slug ? "Editar app" : "Novo app")}
    <form class="panel aside" id="f-app">
      <label for="f-name">Nome *</label><input id="f-name" maxlength="80" required value="${esc(a.name)}">
      <label for="f-desc">Descrição curta</label><input id="f-desc" maxlength="300" value="${esc(a.description)}">
      <div class="row">
        <div><label for="f-cat">Categoria</label><input id="f-cat" maxlength="40" placeholder="Jogo, Utilitário…" value="${esc(a.category)}"></div>
        <div><label for="f-status">Status</label><select id="f-status">
          ${Object.entries(STATUS).map(([k, v]) => `<option value="${k}" ${a.status === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>
      </div>
      <label for="f-tech">Tecnologias <small>(separadas por vírgula)</small></label>
      <input id="f-tech" maxlength="200" placeholder="HTML, CSS, JavaScript" value="${esc(a.tech.join(", "))}">
      <label for="f-url">Link do app <small>(onde ele roda — opcional)</small></label>
      <input id="f-url" type="url" placeholder="https://… ou http://localhost:8080" value="${esc(a.url)}">
      <label for="f-readme">README <small>(Markdown)</small></label>
      <textarea id="f-readme" maxlength="100000">${esc(a.readme)}</textarea>
      <div class="actions"><button type="button" class="btn small" id="f-prev">Ver prévia</button></div>
      <div class="panel md hidden" id="f-prev-box"></div>
      <div class="err" id="f-err" role="alert"></div>
      <div class="actions"><button class="btn primary" id="f-save">${slug ? "Salvar alterações" : "Cadastrar app"}</button>
        <a class="btn" href="${slug ? "#/app/" + encodeURIComponent(slug) : "#/"}">Cancelar</a></div>
    </form>`);
  $("#f-prev").onclick = async () => {
    const box = $("#f-prev-box");
    if (!box.classList.contains("hidden")) { box.classList.add("hidden"); $("#f-prev").textContent = "Ver prévia"; return; }
    try {
      box.innerHTML = (await api("POST", "/api/markdown", { text: $("#f-readme").value })).html || '<p class="muted">Vazio.</p>';
      box.classList.remove("hidden"); $("#f-prev").textContent = "Esconder prévia";
    } catch (e) { toast(e.message, true); }
  };
  $("#f-app").onsubmit = async (ev) => {
    ev.preventDefault();
    const btn = $("#f-save"); btn.disabled = true;
    const body = { name: $("#f-name").value, description: $("#f-desc").value, category: $("#f-cat").value,
      status: $("#f-status").value, tech: $("#f-tech").value, url: $("#f-url").value, readme: $("#f-readme").value };
    try {
      const r = slug ? await api("PUT", `/api/apps/${encodeURIComponent(slug)}`, body) : await api("POST", "/api/apps", body);
      toast(slug ? "Alterações salvas." : "App cadastrado.");
      go(`#/app/${encodeURIComponent(r.slug)}`);
    } catch (e) { $("#f-err").textContent = e.message; btn.disabled = false; }
  };
  $("#f-name").focus();
}

/* ---------- nova versão (upload do código) ---------- */
async function viewNewVersion(slug) {
  if (!ME.admin) return denied();
  const my = navId;
  const { app: a } = await api("GET", `/api/apps/${encodeURIComponent(slug)}`);
  if (my !== navId) return;
  let suggestion = "v1.0";
  if (a.versions.length) {
    const m = /^v?(\d+)\.(\d+)$/.exec(a.versions[0].tag);
    suggestion = m ? `v${m[1]}.${Number(m[2]) + 1}` : "";
  }
  shell(`${head(a.name, "Nova versão")}
    <form class="panel aside" id="f-ver">
      <label for="v-tag">Nome da versão *</label><input id="v-tag" maxlength="30" required value="${esc(suggestion)}" placeholder="v1.0">
      <label for="v-notes">O que mudou <small>(opcional)</small></label>
      <textarea id="v-notes" maxlength="2000" placeholder="Ex.: adicionei skins e corrigi o placar"></textarea>
      <label for="v-dir">Pasta do projeto</label><input id="v-dir" type="file" webkitdirectory multiple>
      <div class="hint">Escolha a pasta inteira do app. Pastas como .git e node_modules são ignoradas.</div>
      <label for="v-files">Ou arquivos soltos / um .zip</label><input id="v-files" type="file" multiple>
      <div class="hint" id="v-info">Limites: 5 MB por arquivo e 50 MB por versão.</div>
      <div class="err" id="v-err" role="alert"></div>
      <div class="actions"><button class="btn primary" id="v-send">Enviar versão</button>
        <a class="btn" href="#/app/${encodeURIComponent(a.slug)}/codigo">Cancelar</a></div>
    </form>`);
  const info = () => {
    const d = $("#v-dir").files.length, f = $("#v-files").files.length;
    $("#v-info").textContent = d ? `${d} arquivos selecionados da pasta.` : f ? `${f} arquivo(s) selecionado(s).`
      : "Limites: 5 MB por arquivo e 50 MB por versão.";
  };
  $("#v-dir").onchange = info; $("#v-files").onchange = info;
  $("#f-ver").onsubmit = async (ev) => {
    ev.preventDefault();
    const dir = [...$("#v-dir").files], loose = [...$("#v-files").files];
    const list = dir.length ? dir : loose;
    if (!list.length) { $("#v-err").textContent = "Escolha uma pasta, arquivos ou um .zip."; return; }
    const fd = new FormData();
    fd.append("tag", $("#v-tag").value); fd.append("notes", $("#v-notes").value);
    for (const f of list) { fd.append("files", f, f.name); fd.append("paths", f.webkitRelativePath || f.name); }
    const btn = $("#v-send"); btn.disabled = true; btn.textContent = "Enviando…"; $("#v-err").textContent = "";
    try {
      const r = await api("POST", `/api/apps/${encodeURIComponent(a.slug)}/versions`, fd, true);
      toast(`Versão enviada (${r.files} arquivos).`);
      go(`#/app/${encodeURIComponent(a.slug)}/codigo`);
    } catch (e) { $("#v-err").textContent = e.message; btn.disabled = false; btn.textContent = "Enviar versão"; }
  };
}

/* ---------- usuários (admin) ---------- */
async function viewUsers() {
  if (!ME.admin) return denied();
  const my = navId;
  const { users } = await api("GET", "/api/users");
  if (my !== navId) return;
  shell(`${head("Administração", "Usuários")}
    <div class="panel aside"><table class="tbl"><thead><tr><th>E-mail</th><th>Cadastro</th><th>Permissão</th><th></th></tr></thead><tbody>
    ${users.map((u) => `<tr><td>${esc(u.email)}</td><td>${fmtDate(u.created_at)}</td>
      <td>${u.admin ? '<span class="pill admin">admin</span>' : '<span class="pill">visualização</span>'}</td>
      <td>${u.admin ? "" : `<button class="btn small ghost danger" data-u="${u.id}" data-e="${esc(u.email)}">Remover</button>`}</td></tr>`).join("")}
    </tbody></table></div>`);
  $$("[data-u]").forEach((b) => b.onclick = async () => {
    if (!(await confirmBox(`Remover o acesso de ${b.dataset.e}?`, "Remover"))) return;
    try { await api("DELETE", `/api/users/${b.dataset.u}`); toast("Usuário removido."); route(); }
    catch (e) { toast(e.message, true); }
  });
}

/* ---------- rotas ---------- */
async function route() {
  const my = ++navId;
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  try {
    if (!ME && parts[0] !== "login") return go("#/login");
    if (ME && parts[0] === "login") return go("#/");
    if (!parts.length) return await viewHome();
    switch (parts[0]) {
      case "login": return viewLogin();
      case "novo": return await viewForm(null);
      case "usuarios": return await viewUsers();
      case "app":
        if (!parts[1]) break;
        if (parts[2] === "editar") return await viewForm(parts[1]);
        if (parts[2] === "versao") return await viewNewVersion(parts[1]);
        return await viewApp(parts[1], parts[2] || "readme");
    }
    go("#/");
  } catch (e) {
    if (my !== navId) return;
    if (e.status === 401) { ME = null; return go("#/login"); }
    showError(e);
  }
}

window.addEventListener("hashchange", route);
(async function init() {
  try { ME = (await api("GET", "/api/me")).user; } catch { ME = null; }
  route();
})();
