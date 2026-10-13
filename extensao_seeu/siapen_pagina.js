// APTO - Ficha do SIAPEN, parte que roda no mundo da página: usa os próprios componentes do SIAPEN (ExtJS) para localizar
// o nome, ler a grade, selecionar a linha, clicar em "Ficha" e fechar a janela da ficha - os mesmos eventos que o SIAPEN
// dispara quando a pessoa digita e clica. Só responde aos pedidos do script da extensão (siapen.js), um de cada vez.
(function () {
  "use strict";
  if (window.__aptoSiapenPg) return;
  window.__aptoSiapenPg = true;
  const ID = {
    consulta: "frmconsultainterno_0",
    localizar: "frmconsultainterno_editlocalizar_0",
    grade: "frmconsultainterno_dbgridconsulta_0",
    selecionado: "frmconsultainterno_unidbtext1_0",
    ficha: "frmconsultainterno_unibitbtnfichadisciplinarinterno_0",
    janelaFicha: "frmvisualizarrelatorio_0",
  };
  const cmp = (id) => (window.Ext && window.Ext.getCmp ? window.Ext.getCmp(id) : null);
  const vivo = (c) => !!(c && !c.isDestroyed);
  let cargas = 0;
  let lojaVigiada = null;

  function vigiarLoja() {
    const g = cmp(ID.grade);
    const st = g && g.getStore && g.getStore();
    if (st && st !== lojaVigiada) {
      st.on("load", () => { cargas++; });
      lojaVigiada = st;
    }
  }
  function ocupado() {
    try { return !!(window.Ext.Ajax && window.Ext.Ajax.isLoading && window.Ext.Ajax.isLoading()); } catch (e) { return false; }
  }
  function rotulo() {
    const l = cmp(ID.selecionado);
    if (vivo(l)) return String((l.text != null ? l.text : (l.el && l.el.dom.textContent)) || "");
    const el = document.getElementById(ID.selecionado);
    return el ? el.textContent : "";
  }
  // colunas pelo título (Nome do Interno, Prontuário, Mãe, ID); se o SIAPEN mudar os títulos, a ordem atual
  function colunas(g) {
    const r = { nome: "0", pront: "1", mae: "2", id: "12" };
    try {
      for (const c of g.headerCt.getGridColumns()) {
        const t = String(c.text || "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase();
        if (/^nome/.test(t)) r.nome = c.dataIndex;
        else if (/^mae/.test(t)) r.mae = c.dataIndex;
        else if (/^prontu/.test(t)) r.pront = c.dataIndex;
        else if (t === "id") r.id = c.dataIndex;
      }
    } catch (e) {}
    return r;
  }

  const ops = {
    estado() {
      vigiarLoja();
      const janela = cmp(ID.janelaFicha);
      return {
        ext: !!window.Ext,
        consulta: vivo(cmp(ID.consulta)) && vivo(cmp(ID.localizar)) && vivo(cmp(ID.grade)) && vivo(cmp(ID.ficha)),
        ocupado: ocupado(), cargas, rotulo: rotulo(), janela: vivo(janela) && janela.isVisible(),
      };
    },
    localizar(a) {
      vigiarLoja();
      const f = cmp(ID.localizar);
      const nome = String(a.nome || "");
      const atual = String(f.getValue() || "");
      if (atual.toUpperCase() === nome.toUpperCase()) f.fireEvent("change", f, nome, "");
      else f.setValue(nome); // dispara o "change" do campo, como a digitação
      return { ok: true };
    },
    linhas() {
      const g = cmp(ID.grade);
      const c = colunas(g);
      const pos = g.getSelectionModel().getCurrentPosition && g.getSelectionModel().getCurrentPosition();
      return {
        atual: pos && pos.row != null ? pos.row : -1,
        linhas: g.getStore().getRange().map((r, i) => ({ i, nome: String(r.get(c.nome) || ""), pront: String(r.get(c.pront) || ""), mae: String(r.get(c.mae) || ""), id: String(r.get(c.id) || "") })),
      };
    },
    selecionar(a) {
      const g = cmp(ID.grade);
      const sm = g.getSelectionModel();
      const pos = sm.getCurrentPosition && sm.getCurrentPosition();
      if (pos && pos.row === a.i) return { ok: true, ja: true };
      sm.setCurrentPosition({ row: a.i, column: 0 }); // dispara o "select" da grade, como o clique na linha
      return { ok: true };
    },
    ficha() {
      const b = cmp(ID.ficha);
      if (b.isDisabled && b.isDisabled()) return { ok: false, motivo: "botão Ficha desabilitado" };
      b.fireEvent("click", b, window.Ext.EventObject);
      return { ok: true };
    },
    fechar() {
      const w = cmp(ID.janelaFicha);
      if (vivo(w)) w.close();
      return { ok: true };
    },
  };

  document.addEventListener("apto-siapen-pedido", (e) => {
    let q;
    try { q = JSON.parse(e.detail); } catch (x) { return; }
    let r;
    try {
      if (!window.Ext || !ops[q.op]) r = { erro: "sem ExtJS" };
      else if (q.op !== "estado" && !ops.estado().consulta) r = { erro: "consulta fechada" };
      else r = ops[q.op](q.args || {});
    } catch (x) {
      r = { erro: String((x && x.message) || x) };
    }
    document.dispatchEvent(new CustomEvent("apto-siapen-resposta", { detail: JSON.stringify({ id: q.id, r }) }));
  });
})();
