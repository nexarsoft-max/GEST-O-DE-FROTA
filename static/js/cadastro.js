  // Anti-conflito: captura o clique e força o destino certo,
  // impedindo qualquer JS externo de redirecionar para outra rota.
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a.botao-cadastrar");
    if (!a) return;

    e.preventDefault();
    e.stopPropagation();

    const destino = a.getAttribute("data-destino") || a.getAttribute("href");
    document.body.classList.add("page-exit");

    setTimeout(() => window.location.assign(destino), 150);
  }, true);