  document.querySelectorAll('.card-registro button').forEach(btn => {
    btn.addEventListener('click', e => {
      const destino = e.currentTarget.dataset.destino;
      document.body.classList.add("page-exit");
      setTimeout(() => {
        window.location.href = destino;
      }, 150);
    });
  });