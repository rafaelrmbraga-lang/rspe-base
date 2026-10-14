"""Conversor de Áudio — extrai o áudio de vídeos (MP4, MKV, MOV...) para MP3 e outros formatos.

Feito para reuniões longas: o modo "NotebookLM" gera um MP3 de voz compacto
(~29 MB por hora) e, se ainda passar do limite de upload, divide em partes.
O ffmpeg vem embutido (pacote imageio-ffmpeg), então não precisa instalar nada.
"""
import math
import os
import re
import subprocess
import sys
import threading

VERSAO = "1.0.0"

# Limite de upload por arquivo no NotebookLM é 200 MB; folga para não bater no teto.
LIMITE_MB = 190

# nome exibido -> (extensão, argumentos de áudio do ffmpeg, kbps estimado ou None)
FORMATOS = {
    "NotebookLM — MP3 de voz, compacto (recomendado)": ("mp3", ["-ac", "1", "-ar", "22050", "-c:a", "libmp3lame", "-b:a", "64k"], 64),
    "MP3 — qualidade alta (192 kbps)": ("mp3", ["-ac", "2", "-c:a", "libmp3lame", "-b:a", "192k"], 192),
    "M4A (AAC) — 128 kbps": ("m4a", ["-c:a", "aac", "-b:a", "128k"], 128),
    "OGG (Vorbis) — boa qualidade": ("ogg", ["-c:a", "libvorbis", "-q:a", "5"], 160),
    "WAV — sem compressão (arquivo grande)": ("wav", ["-c:a", "pcm_s16le"], 1411),
    "FLAC — sem perda": ("flac", ["-c:a", "flac"], 800),
}
FORMATO_PADRAO = next(iter(FORMATOS))

_SEM_JANELA = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
_PROCESSOS = set()  # ffmpeg em execução, para encerrar se a janela for fechada


def caminho_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"  # cai para o ffmpeg do sistema, se houver


def duracao_segundos(ffmpeg, arquivo):
    """Lê a duração do arquivo pela saída de `ffmpeg -i`. Retorna None se não achar."""
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", arquivo], capture_output=True,
                       text=True, errors="replace", creationflags=_SEM_JANELA)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def nome_livre(caminho):
    """Evita sobrescrever: 'reuniao.mp3' -> 'reuniao (1).mp3' se já existir."""
    base, ext = os.path.splitext(caminho)
    n = 1
    while os.path.exists(caminho):
        caminho = f"{base} ({n}){ext}"
        n += 1
    return caminho


def planejar_partes(duracao, kbps, dividir):
    """Quantas partes são necessárias para cada uma ficar abaixo do limite."""
    if not dividir or not duracao:
        return 1
    tamanho_mb = duracao * kbps / 8 / 1024
    return max(1, math.ceil(tamanho_mb / LIMITE_MB))


def converter(arquivo, formato, pasta_saida=None, dividir=True, ao_progresso=None, cancelado=None):
    """Converte um arquivo. Retorna a lista de arquivos gerados.

    ao_progresso(fracao 0..1) é chamado durante a conversão;
    cancelado() -> True interrompe e apaga o que foi gerado.
    """
    ffmpeg = caminho_ffmpeg()
    ext, args_audio, kbps = FORMATOS[formato]
    pasta = pasta_saida or os.path.dirname(os.path.abspath(arquivo))
    nome = os.path.splitext(os.path.basename(arquivo))[0]
    duracao = duracao_segundos(ffmpeg, arquivo)
    partes = planejar_partes(duracao, kbps, dividir)

    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", arquivo, "-vn", "-sn", "-dn"] + args_audio
    if partes > 1:
        prefixo = f"{nome} - parte "
        n = 1
        while any(os.path.exists(os.path.join(pasta, f"{prefixo}{i:02d}.{ext}")) for i in range(1, partes + 2)):
            prefixo = f"{nome} ({n}) - parte "
            n += 1
        segmento = math.ceil(duracao / partes) + 1
        destino_padrao = os.path.join(pasta, f"{prefixo}%02d.{ext}")
        cmd += ["-f", "segment", "-segment_time", str(segmento), "-segment_start_number", "1",
                "-reset_timestamps", "1", destino_padrao]
        gerados = lambda: sorted(  # noqa: E731
            os.path.join(pasta, f) for f in os.listdir(pasta)
            if f.startswith(prefixo) and f.endswith("." + ext))
    else:
        destino = nome_livre(os.path.join(pasta, f"{nome}.{ext}"))
        cmd.append(destino)
        gerados = lambda: [destino] if os.path.exists(destino) else []  # noqa: E731

    cmd[1:1] = ["-progress", "pipe:1", "-nostats", "-loglevel", "error"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            errors="replace", creationflags=_SEM_JANELA)
    _PROCESSOS.add(proc)
    erros = []
    leitor_erros = threading.Thread(target=lambda: erros.extend(proc.stderr), daemon=True)
    leitor_erros.start()

    for linha in proc.stdout:
        if cancelado and cancelado():
            proc.kill()
            proc.wait()
            for f in gerados():
                try:
                    os.remove(f)
                except OSError:
                    pass
            raise InterruptedError("Conversão cancelada.")
        if linha.startswith("out_time_us=") and duracao and ao_progresso:
            try:
                ao_progresso(min(1.0, int(linha.split("=", 1)[1]) / 1e6 / duracao))
            except ValueError:
                pass
    proc.wait()
    _PROCESSOS.discard(proc)
    leitor_erros.join(timeout=2)
    if proc.returncode != 0:
        msg = "".join(erros).strip() or f"ffmpeg terminou com código {proc.returncode}"
        if "does not contain any stream" in msg or "Output file #0 does not contain" in msg:
            msg = "Este arquivo não tem faixa de áudio."
        raise RuntimeError(msg[-600:])
    if ao_progresso:
        ao_progresso(1.0)
    return gerados()


def _tamanho(caminho):
    mb = os.path.getsize(caminho) / 1024 / 1024
    return f"{mb / 1024:.2f} GB" if mb >= 1024 else f"{mb:.1f} MB"


# ----------------------------------------------------------------- interface

def app():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    raiz = tk.Tk()
    raiz.title("Conversor de Áudio")
    raiz.geometry("620x470")
    raiz.minsize(520, 430)
    try:
        ttk.Style().theme_use("vista" if sys.platform == "win32" else "clam")
    except tk.TclError:
        pass

    arquivos = []
    pasta_saida = tk.StringVar(value="")
    formato = tk.StringVar(value=FORMATO_PADRAO)
    dividir = tk.BooleanVar(value=True)
    status = tk.StringVar(value="Escolha um ou mais vídeos para começar.")
    estado = {"cancelar": False, "rodando": False}

    quadro = ttk.Frame(raiz, padding=16)
    quadro.pack(fill="both", expand=True)
    fonte_titulo = ("Segoe UI", 13, "bold") if sys.platform == "win32" else ("TkDefaultFont", 13, "bold")

    # 1. Arquivos
    ttk.Label(quadro, text="1. Arquivos", font=fonte_titulo).pack(anchor="w")
    linha1 = ttk.Frame(quadro)
    linha1.pack(fill="x", pady=(4, 10))
    lista = tk.Listbox(linha1, height=5, activestyle="none")
    lista.pack(side="left", fill="both", expand=True)
    botoes_arq = ttk.Frame(linha1)
    botoes_arq.pack(side="left", padx=(8, 0), anchor="n")

    def escolher():
        tipos = [("Vídeos e áudios", "*.mp4 *.mkv *.mov *.avi *.webm *.wmv *.m4v *.mpg *.mpeg *.3gp "
                  "*.mp3 *.m4a *.wav *.ogg *.flac *.aac *.wma *.opus"), ("Todos os arquivos", "*.*")]
        for f in filedialog.askopenfilenames(title="Escolha os arquivos", filetypes=tipos):
            if f not in arquivos:
                arquivos.append(f)
                lista.insert("end", f"{os.path.basename(f)}   ({_tamanho(f)})")
        if arquivos:
            status.set(f"{len(arquivos)} arquivo(s) na lista. Clique em Converter.")

    def limpar():
        arquivos.clear()
        lista.delete(0, "end")
        status.set("Escolha um ou mais vídeos para começar.")

    b_escolher = ttk.Button(botoes_arq, text="Escolher…", command=escolher)
    b_escolher.pack(fill="x")
    b_limpar = ttk.Button(botoes_arq, text="Limpar", command=limpar)
    b_limpar.pack(fill="x", pady=(6, 0))

    # 2. Formato
    ttk.Label(quadro, text="2. Formato", font=fonte_titulo).pack(anchor="w")
    combo = ttk.Combobox(quadro, textvariable=formato, values=list(FORMATOS), state="readonly")
    combo.pack(fill="x", pady=(4, 4))
    ck = ttk.Checkbutton(quadro, variable=dividir,
                         text=f"Dividir em partes se passar de {LIMITE_MB} MB (limite do NotebookLM é 200 MB)")
    ck.pack(anchor="w", pady=(0, 10))

    # 3. Destino
    ttk.Label(quadro, text="3. Onde salvar", font=fonte_titulo).pack(anchor="w")
    linha3 = ttk.Frame(quadro)
    linha3.pack(fill="x", pady=(4, 12))
    rotulo_pasta = ttk.Label(linha3, text="Mesma pasta do arquivo original", foreground="#555")
    rotulo_pasta.pack(side="left", fill="x", expand=True)

    def escolher_pasta():
        p = filedialog.askdirectory(title="Pasta de destino")
        if p:
            pasta_saida.set(p)
            rotulo_pasta.config(text=p)

    b_pasta = ttk.Button(linha3, text="Mudar…", command=escolher_pasta)
    b_pasta.pack(side="left")

    # Progresso
    barra = ttk.Progressbar(quadro, maximum=1000)
    barra.pack(fill="x")
    ttk.Label(quadro, textvariable=status, wraplength=580).pack(anchor="w", pady=(6, 10))

    linha_acao = ttk.Frame(quadro)
    linha_acao.pack(fill="x", side="bottom")
    b_converter = ttk.Button(linha_acao, text="Converter")
    b_converter.pack(side="right")
    b_abrir = ttk.Button(linha_acao, text="Abrir pasta", state="disabled")
    b_abrir.pack(side="right", padx=(0, 8))
    ultima_pasta = {"p": None}

    def abrir_pasta():
        p = ultima_pasta["p"]
        if not p:
            return
        if sys.platform == "win32":
            os.startfile(p)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", p])

    b_abrir.config(command=abrir_pasta)

    def travar(rodando):
        estado["rodando"] = rodando
        s = "disabled" if rodando else "normal"
        for w in (b_escolher, b_limpar, b_pasta, ck):
            w.config(state=s)
        combo.config(state="disabled" if rodando else "readonly")
        b_converter.config(text="Cancelar" if rodando else "Converter")

    def trabalhar(fila, fmt, pasta, div):
        feitos, falhas = [], []
        for i, arq in enumerate(fila, 1):
            prefixo = f"[{i}/{len(fila)}] {os.path.basename(arq)}"
            raiz.after(0, status.set, f"{prefixo} — preparando…")

            def prog(fr, prefixo=prefixo):
                raiz.after(0, barra.config, {"value": fr * 1000})
                raiz.after(0, status.set, f"{prefixo} — {fr * 100:.0f}%")
            try:
                feitos += converter(arq, fmt, pasta, div, prog, lambda: estado["cancelar"])
            except InterruptedError:
                raiz.after(0, fim, feitos, falhas, True)
                return
            except Exception as e:  # mostra o erro e segue para o próximo
                falhas.append(f"{os.path.basename(arq)}: {e}")
        raiz.after(0, fim, feitos, falhas, False)

    def fim(feitos, falhas, cancelado):
        travar(False)
        if feitos:
            ultima_pasta["p"] = os.path.dirname(feitos[0])
            b_abrir.config(state="normal")
        if cancelado:
            barra.config(value=0)
            status.set("Cancelado.")
            return
        resumo = "\n".join(f"• {os.path.basename(f)}  ({_tamanho(f)})" for f in feitos)
        status.set(f"Pronto! {len(feitos)} arquivo(s) gerado(s)." if feitos else "Nada foi gerado.")
        if falhas:
            messagebox.showwarning("Conversor de Áudio",
                                   (f"Gerados:\n{resumo}\n\n" if feitos else "") + "Problemas:\n" + "\n".join(falhas))
        elif feitos:
            messagebox.showinfo("Conversor de Áudio", f"Conversão concluída!\n\n{resumo}")

    def converter_clique():
        if estado["rodando"]:
            estado["cancelar"] = True
            status.set("Cancelando…")
            return
        if not arquivos:
            escolher()
            if not arquivos:
                return
        estado["cancelar"] = False
        barra.config(value=0)
        travar(True)
        threading.Thread(target=trabalhar, daemon=True,
                         args=(list(arquivos), formato.get(), pasta_saida.get() or None, dividir.get())).start()

    b_converter.config(command=converter_clique)

    def fechar():
        if estado["rodando"] and not messagebox.askyesno("Conversor de Áudio", "Uma conversão está em andamento. Cancelar e sair?"):
            return
        estado["cancelar"] = True
        for p in list(_PROCESSOS):
            p.kill()
        raiz.destroy()

    raiz.protocol("WM_DELETE_WINDOW", fechar)
    raiz.mainloop()


if __name__ == "__main__":
    app()
