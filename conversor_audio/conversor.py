"""Conversor de Áudio — extrai o áudio de vídeos (MP4, MKV, MOV...) para MP3 e outros formatos, ou converte para WebM.

O usuário escolhe o formato e o nível de compressão, de "sem perda nenhuma"
(áudio original sem recomprimir, FLAC, WAV) até "voz compacta". Preparado para
arquivos grandes (vários GB, muitas horas): o ffmpeg lê em fluxo, sem carregar
o arquivo na memória, e o programa mostra tempo restante e tamanho estimado.
Se a saída passar do limite de upload do NotebookLM, divide em partes.
O ffmpeg vem embutido (pacote imageio-ffmpeg), então não precisa instalar nada.
"""
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time

VERSAO = "1.2.0"

# Limite de upload por arquivo no NotebookLM é 200 MB; folga para não bater no teto.
LIMITE_MB = 190

ORIGINAL = "Original do vídeo — sem recomprimir"


def _vp9(altura_max, taxa):
    """Vídeo VP9 em modo rápido (realtime) + áudio Opus. Não aumenta vídeos menores que altura_max."""
    return ["-vf", f"scale=-2:'min({altura_max},ih)'", "-c:v", "libvpx-vp9", "-b:v", taxa,
            "-maxrate", taxa, "-bufsize", taxa, "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1",
            "-g", "300", "-c:a", "libopus", "-b:a", "96k"]

# formato -> (extensão, {qualidade: (argumentos de áudio do ffmpeg, kbps)})
# kbps None = calculado a partir do áudio de origem.
FORMATOS = {
    "MP3": ("mp3", {
        "Boa — 128 kbps (recomendado para reuniões)": (["-c:a", "libmp3lame", "-b:a", "128k"], 128),
        "Alta — 192 kbps": (["-c:a", "libmp3lame", "-b:a", "192k"], 192),
        "Máxima — 320 kbps": (["-c:a", "libmp3lame", "-b:a", "320k"], 320),
        "Voz compacta — 64 kbps mono (arquivo menor)": (["-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k"], 64),
    }),
    ORIGINAL: (None, {
        "Sem perda nenhuma — copia o áudio como está (mais rápido)": (["-c:a", "copy"], None),
    }),
    "M4A (AAC)": ("m4a", {
        "Boa — 128 kbps": (["-c:a", "aac", "-b:a", "128k"], 128),
        "Alta — 256 kbps": (["-c:a", "aac", "-b:a", "256k"], 256),
        "Compacta — 96 kbps": (["-c:a", "aac", "-b:a", "96k"], 96),
    }),
    "OGG (Vorbis)": ("ogg", {
        "Boa — qualidade 5 (~160 kbps)": (["-c:a", "libvorbis", "-q:a", "5"], 160),
        "Alta — qualidade 8 (~256 kbps)": (["-c:a", "libvorbis", "-q:a", "8"], 256),
        "Compacta — qualidade 3 (~112 kbps)": (["-c:a", "libvorbis", "-q:a", "3"], 112),
    }),
    "WebM — só áudio (Opus)": ("webm", {
        "Boa — 96 kbps": (["-c:a", "libopus", "-b:a", "96k"], 96),
        "Alta — 160 kbps": (["-c:a", "libopus", "-b:a", "160k"], 160),
        "Voz compacta — 32 kbps mono (arquivo bem menor)": (["-ac", "1", "-c:a", "libopus", "-b:a", "32k"], 32),
    }),
    "WebM — com vídeo (VP9)": ("webm", {
        "Boa — até 720p (~1 Mbps)": (_vp9(720, "1M"), 1000 + 96),
        "Compacta — até 480p (~500 kbps)": (_vp9(480, "500k"), 500 + 96),
        "Alta — até 1080p (~2,5 Mbps, mais lento)": (_vp9(1080, "2500k"), 2500 + 96),
    }),
    "FLAC (compressão sem perda)": ("flac", {
        "Normal — nível 5": (["-c:a", "flac", "-compression_level", "5"], None),
        "Máxima compressão — nível 8 (mais lento, mesma qualidade)": (["-c:a", "flac", "-compression_level", "8"], None),
    }),
    "WAV (sem compressão)": ("wav", {
        "PCM 16 bits — qualidade de CD": (["-c:a", "pcm_s16le"], None),
    }),
}
FORMATO_PADRAO = "MP3"

# áudio copiado sem recomprimir: o contêiner depende do codec que está no vídeo
_EXT_COPIA = {"aac": "m4a", "mp3": "mp3", "vorbis": "ogg", "opus": "ogg", "flac": "flac", "alac": "m4a"}

_SEM_JANELA = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
_PROCESSOS = set()  # ffmpeg em execução, para encerrar se a janela for fechada


def caminho_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"  # cai para o ffmpeg do sistema, se houver


def analisar(arquivo, ffmpeg=None):
    """Lê duração e dados da 1ª faixa de áudio pela saída de `ffmpeg -i` (só o cabeçalho; rápido mesmo em 3 GB)."""
    r = subprocess.run([ffmpeg or caminho_ffmpeg(), "-hide_banner", "-i", arquivo], capture_output=True,
                       text=True, errors="replace", creationflags=_SEM_JANELA)
    info = {"duracao": None, "codec": None, "kbps": None, "hz": 44100, "canais": 2,
            "video": any("Stream #" in l and "Video:" in l and "attached pic" not in l for l in r.stderr.splitlines())}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if m:
        h, mi, s = m.groups()
        info["duracao"] = int(h) * 3600 + int(mi) * 60 + float(s)
    audio = next((l for l in r.stderr.splitlines() if "Stream #" in l and "Audio:" in l), None)
    if audio:
        info["codec"] = re.search(r"Audio:\s*(\w+)", audio).group(1)
        if m := re.search(r"(\d+) Hz", audio):
            info["hz"] = int(m.group(1))
        if m := re.search(r"(\d+) kb/s", audio):
            info["kbps"] = int(m.group(1))
        info["canais"] = 1 if ", mono" in audio else 6 if "5.1" in audio else 2
    return info


def extensao(formato, info):
    ext = FORMATOS[formato][0]
    if ext is None:  # cópia sem recomprimir
        c = info.get("codec") or ""
        ext = "wav" if c.startswith("pcm_") else _EXT_COPIA.get(c, "mka")
    return ext


def kbps_saida(formato, qualidade, info):
    """Taxa estimada da saída, para prever tamanho."""
    args, kbps = FORMATOS[formato][1][qualidade]
    if kbps:
        return kbps
    pcm = info["hz"] * info["canais"] * 16 / 1000
    if "flac" in args:
        return pcm * 0.6
    if "copy" in args:
        return info.get("kbps") or 128
    return pcm


def tamanho_estimado_mb(formato, qualidade, info):
    if not info.get("duracao"):
        return None
    return info["duracao"] * kbps_saida(formato, qualidade, info) / 8 / 1024


def planejar_partes(tamanho_mb, dividir):
    """Quantas partes são necessárias para cada uma ficar abaixo do limite."""
    if not dividir or not tamanho_mb:
        return 1
    return max(1, math.ceil(tamanho_mb / LIMITE_MB))


def nome_livre(caminho):
    """Evita sobrescrever: 'reuniao.mp3' -> 'reuniao (1).mp3' se já existir."""
    base, ext = os.path.splitext(caminho)
    n = 1
    while os.path.exists(caminho):
        caminho = f"{base} ({n}){ext}"
        n += 1
    return caminho


def converter(arquivo, formato, qualidade, pasta_saida=None, dividir=True, ao_progresso=None,
              cancelado=None, info=None):
    """Converte um arquivo. Retorna a lista de arquivos gerados.

    ao_progresso(fracao 0..1) é chamado durante a conversão;
    cancelado() -> True interrompe e apaga o que foi gerado.
    """
    ffmpeg = caminho_ffmpeg()
    info = info or analisar(arquivo, ffmpeg)
    if not info["codec"]:
        raise RuntimeError("Este arquivo não tem faixa de áudio.")
    args_saida = FORMATOS[formato][1][qualidade][0]
    if "-c:v" in args_saida and not info.get("video"):
        raise RuntimeError("Este arquivo não tem vídeo. Use \"WebM — só áudio\".")
    ext = extensao(formato, info)
    pasta = pasta_saida or os.path.dirname(os.path.abspath(arquivo))
    nome = os.path.splitext(os.path.basename(arquivo))[0]
    duracao = info["duracao"]
    partes = planejar_partes(tamanho_estimado_mb(formato, qualidade, info), dividir)

    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-progress", "pipe:1", "-nostats", "-loglevel", "error",
           "-i", arquivo]
    if "-c:v" in args_saida:  # saída com vídeo
        cmd += ["-map", "0:v:0", "-map", "0:a:0", "-sn", "-dn"] + args_saida
    else:
        cmd += ["-map", "0:a:0", "-vn", "-sn", "-dn"] + args_saida
    if partes > 1:
        prefixo = f"{nome} - parte "
        n = 1
        while any(os.path.exists(os.path.join(pasta, f"{prefixo}{i:02d}.{ext}")) for i in range(1, partes + 2)):
            prefixo = f"{nome} ({n}) - parte "
            n += 1
        segmento = math.ceil(duracao / partes) + 1
        cmd += ["-f", "segment", "-segment_time", str(segmento), "-segment_start_number", "1",
                "-reset_timestamps", "1", os.path.join(pasta, f"{prefixo}%02d.{ext}")]
        gerados = lambda: sorted(  # noqa: E731
            os.path.join(pasta, f) for f in os.listdir(pasta)
            if f.startswith(prefixo) and f.endswith("." + ext))
    else:
        destino = nome_livre(os.path.join(pasta, f"{nome}.{ext}"))
        cmd.append(destino)
        gerados = lambda: [destino] if os.path.exists(destino) else []  # noqa: E731

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            errors="replace", creationflags=_SEM_JANELA)
    _PROCESSOS.add(proc)
    erros = []
    leitor_erros = threading.Thread(target=lambda: erros.extend(proc.stderr), daemon=True)
    leitor_erros.start()

    try:
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
                    ao_progresso(min(1.0, max(0, int(linha.split("=", 1)[1])) / 1e6 / duracao))
                except ValueError:
                    pass
        proc.wait()
    finally:
        _PROCESSOS.discard(proc)
    leitor_erros.join(timeout=2)
    if proc.returncode != 0:
        msg = "".join(erros).strip() or f"ffmpeg terminou com código {proc.returncode}"
        if "No space left" in msg:
            msg = "Disco cheio: libere espaço ou escolha outra pasta de destino."
        raise RuntimeError(msg[-600:])
    if ao_progresso:
        ao_progresso(1.0)
    return gerados()


def fmt_tamanho(mb):
    return f"{mb / 1024:.2f} GB" if mb >= 1024 else f"{mb:.0f} MB" if mb >= 10 else f"{mb:.1f} MB"


def fmt_tempo(seg):
    seg = int(round(seg))
    h, m, s = seg // 3600, seg % 3600 // 60, seg % 60
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"


class Cronometro:
    """Estima o tempo restante pela velocidade média (estável em arquivos longos)."""

    def __init__(self, total_seg):
        self.total = total_seg or 0
        self.inicio = time.monotonic()

    def texto(self, feito_seg):
        dec = time.monotonic() - self.inicio
        t = f"decorrido {fmt_tempo(dec)}"
        if self.total and feito_seg > 0 and dec >= 3:
            vel = feito_seg / dec
            t += f" · faltam ~{fmt_tempo(max(0, self.total - feito_seg) / vel)} · {vel:.0f}x mais rápido que o tempo real"
        elif self.total:
            t += " · calculando tempo restante…"
        return t


# ----------------------------------------------------------------- interface

def app():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    raiz = tk.Tk()
    raiz.title(f"Conversor de Áudio {VERSAO}")
    raiz.geometry("680x600")
    raiz.minsize(580, 560)
    try:
        ttk.Style().theme_use("vista" if sys.platform == "win32" else "clam")
    except tk.TclError:
        pass

    arquivos = []   # caminhos
    infos = {}      # caminho -> analisar()
    pasta_saida = tk.StringVar(value="")
    formato = tk.StringVar(value=FORMATO_PADRAO)
    qualidade = tk.StringVar(value=next(iter(FORMATOS[FORMATO_PADRAO][1])))
    dividir = tk.BooleanVar(value=True)
    status = tk.StringVar(value="Escolha um ou mais vídeos para começar.")
    detalhe = tk.StringVar(value="")
    estimativa = tk.StringVar(value="")
    estado = {"cancelar": False, "rodando": False}

    quadro = ttk.Frame(raiz, padding=16)
    quadro.pack(fill="both", expand=True)
    fonte_titulo = ("Segoe UI", 12, "bold") if sys.platform == "win32" else ("TkDefaultFont", 12, "bold")

    # 1. Arquivos
    ttk.Label(quadro, text="1. Arquivos", font=fonte_titulo).pack(anchor="w")
    linha1 = ttk.Frame(quadro)
    linha1.pack(fill="x", pady=(4, 10))
    lista = tk.Listbox(linha1, height=5, activestyle="none")
    lista.pack(side="left", fill="both", expand=True)
    botoes_arq = ttk.Frame(linha1)
    botoes_arq.pack(side="left", padx=(8, 0), anchor="n")

    def rotulo_arquivo(f):
        i = infos.get(f)
        mb = os.path.getsize(f) / 1024 / 1024
        if i is None:
            extra = "lendo…"
        elif not i["codec"]:
            extra = "sem áudio!"
        else:
            extra = fmt_tempo(i["duracao"]) if i["duracao"] else "duração desconhecida"
        return f"{os.path.basename(f)}   ({fmt_tamanho(mb)} · {extra})"

    def atualizar_lista():
        lista.delete(0, "end")
        for f in arquivos:
            lista.insert("end", rotulo_arquivo(f))
        atualizar_estimativa()

    def ler_infos(novos):
        for f in novos:
            try:
                infos[f] = analisar(f)
            except Exception:
                infos[f] = {"duracao": None, "codec": None, "kbps": None, "hz": 44100, "canais": 2, "video": False}
        raiz.after(0, atualizar_lista)

    def escolher():
        tipos = [("Vídeos e áudios", "*.mp4 *.mkv *.mov *.avi *.webm *.wmv *.m4v *.mpg *.mpeg *.3gp *.ts "
                  "*.mp3 *.m4a *.wav *.ogg *.flac *.aac *.wma *.opus"), ("Todos os arquivos", "*.*")]
        novos = [f for f in filedialog.askopenfilenames(title="Escolha os arquivos", filetypes=tipos)
                 if f not in arquivos]
        arquivos.extend(novos)
        atualizar_lista()
        if novos:
            threading.Thread(target=ler_infos, args=(novos,), daemon=True).start()

    def limpar():
        arquivos.clear()
        atualizar_lista()

    b_escolher = ttk.Button(botoes_arq, text="Escolher…", command=escolher)
    b_escolher.pack(fill="x")
    b_limpar = ttk.Button(botoes_arq, text="Limpar", command=limpar)
    b_limpar.pack(fill="x", pady=(6, 0))

    # 2. Formato e compressão
    ttk.Label(quadro, text="2. Formato e compressão", font=fonte_titulo).pack(anchor="w")
    grade = ttk.Frame(quadro)
    grade.pack(fill="x", pady=(4, 2))
    grade.columnconfigure(1, weight=1)
    ttk.Label(grade, text="Formato:").grid(row=0, column=0, sticky="w", padx=(0, 8))
    combo_fmt = ttk.Combobox(grade, textvariable=formato, values=list(FORMATOS), state="readonly")
    combo_fmt.grid(row=0, column=1, sticky="ew")
    ttk.Label(grade, text="Qualidade:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
    combo_q = ttk.Combobox(grade, textvariable=qualidade, state="readonly")
    combo_q.grid(row=1, column=1, sticky="ew", pady=(6, 0))
    ttk.Label(quadro, textvariable=estimativa, foreground="#1a5d1a", wraplength=630).pack(anchor="w", pady=(6, 2))
    ck = ttk.Checkbutton(quadro, variable=dividir,
                         text=f"Dividir em partes se passar de {LIMITE_MB} MB (limite do NotebookLM é 200 MB por arquivo)")
    ck.pack(anchor="w", pady=(0, 10))

    def total_estimado():
        mb, seg, desconhecido = 0, 0, False
        for f in arquivos:
            i = infos.get(f)
            t = tamanho_estimado_mb(formato.get(), qualidade.get(), i) if i and i["codec"] else None
            if t is None:
                desconhecido = True
            else:
                mb += t
                seg += i["duracao"]
        return mb, seg, desconhecido

    def atualizar_estimativa(*_):
        if not arquivos:
            estimativa.set("")
            status.set("Escolha um ou mais vídeos para começar.")
            return
        mb, seg, desc = total_estimado()
        if not mb:
            estimativa.set("Lendo os arquivos…" if desc else "")
        else:
            partes = sum(planejar_partes(tamanho_estimado_mb(formato.get(), qualidade.get(), infos[f]), dividir.get())
                         for f in arquivos if infos.get(f) and infos[f]["codec"] and infos[f]["duracao"])
            txt = f"Resultado estimado: ~{fmt_tamanho(mb)} para {fmt_tempo(seg)} de áudio"
            if partes > len(arquivos):
                txt += f" (em {partes} partes)"
            estimativa.set(txt + ("" if not desc else " — alguns arquivos ainda sem estimativa"))
        if not estado["rodando"]:
            status.set(f"{len(arquivos)} arquivo(s) na lista. Clique em Converter.")

    def trocar_formato(*_):
        opcoes = list(FORMATOS[formato.get()][1])
        combo_q.config(values=opcoes)
        if qualidade.get() not in opcoes:
            qualidade.set(opcoes[0])
        atualizar_estimativa()

    combo_fmt.bind("<<ComboboxSelected>>", trocar_formato)
    combo_q.bind("<<ComboboxSelected>>", atualizar_estimativa)
    dividir.trace_add("write", atualizar_estimativa)
    trocar_formato()

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
    ttk.Label(quadro, textvariable=status, wraplength=630).pack(anchor="w", pady=(6, 0))
    ttk.Label(quadro, textvariable=detalhe, wraplength=630, foreground="#555").pack(anchor="w", pady=(2, 10))

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
        for c in (combo_fmt, combo_q):
            c.config(state="disabled" if rodando else "readonly")
        b_converter.config(text="Cancelar" if rodando else "Converter")

    def trabalhar(fila, fmt, q, pasta, div):
        feitos, falhas = [], []
        total = sum((infos[f]["duracao"] or 0) for f in fila)
        crono = Cronometro(total)
        ja_feito = 0.0
        for i, arq in enumerate(fila, 1):
            prefixo = f"Arquivo {i} de {len(fila)}: {os.path.basename(arq)}"
            dur = infos[arq]["duracao"] or 0
            raiz.after(0, status.set, f"{prefixo} — iniciando…")

            def prog(fr, prefixo=prefixo, base=ja_feito, dur=dur):
                feito = base + fr * dur
                geral = feito / total if total else fr
                raiz.after(0, barra.config, {"value": geral * 1000})
                raiz.after(0, status.set, f"{prefixo} — {fr * 100:.0f}%" + (f" (total {geral * 100:.0f}%)" if len(fila) > 1 else ""))
                raiz.after(0, detalhe.set, crono.texto(feito))
            try:
                feitos += converter(arq, fmt, q, pasta, div, prog, lambda: estado["cancelar"], infos[arq])
            except InterruptedError:
                raiz.after(0, fim, feitos, falhas, True, crono)
                return
            except Exception as e:  # mostra o erro e segue para o próximo
                falhas.append(f"{os.path.basename(arq)}: {e}")
            ja_feito += dur
        raiz.after(0, fim, feitos, falhas, False, crono)

    def fim(feitos, falhas, cancelado, crono):
        travar(False)
        if feitos:
            ultima_pasta["p"] = os.path.dirname(feitos[0])
            b_abrir.config(state="normal")
        gasto = fmt_tempo(time.monotonic() - crono.inicio)
        if cancelado:
            barra.config(value=0)
            status.set("Cancelado.")
            detalhe.set("")
            return
        resumo = "\n".join(f"• {os.path.basename(f)}  ({fmt_tamanho(os.path.getsize(f) / 1024 / 1024)})" for f in feitos)
        status.set(f"Pronto! {len(feitos)} arquivo(s) gerado(s)." if feitos else "Nada foi gerado.")
        detalhe.set(f"Tempo total: {gasto}")
        if falhas:
            messagebox.showwarning("Conversor de Áudio",
                                   (f"Gerados:\n{resumo}\n\n" if feitos else "") + "Problemas:\n" + "\n".join(falhas))
        elif feitos:
            messagebox.showinfo("Conversor de Áudio", f"Conversão concluída em {gasto}!\n\n{resumo}")

    def espaco_ok(fila):
        """Avisa se a pasta de destino não tem espaço para o resultado estimado."""
        por_pasta = {}
        for f in fila:
            p = pasta_saida.get() or os.path.dirname(os.path.abspath(f))
            por_pasta[p] = por_pasta.get(p, 0) + (tamanho_estimado_mb(formato.get(), qualidade.get(), infos[f]) or 0)
        for p, mb in por_pasta.items():
            livre = shutil.disk_usage(p).free / 1024 / 1024
            if mb * 1.1 > livre:
                return messagebox.askyesno(
                    "Conversor de Áudio",
                    f"Pouco espaço em disco em:\n{p}\n\nLivre: {fmt_tamanho(livre)}\nNecessário: ~{fmt_tamanho(mb)}\n\n"
                    "Continuar mesmo assim?")
        return True

    def converter_clique():
        if estado["rodando"]:
            estado["cancelar"] = True
            status.set("Cancelando…")
            return
        if not arquivos:
            escolher()
            return
        if any(f not in infos for f in arquivos):
            status.set("Aguarde: ainda lendo os arquivos…")
            return
        fila = [f for f in arquivos if infos[f]["codec"]]
        sem_audio = [os.path.basename(f) for f in arquivos if not infos[f]["codec"]]
        if sem_audio:
            messagebox.showwarning("Conversor de Áudio", "Sem faixa de áudio (serão ignorados):\n" + "\n".join(sem_audio))
        if not fila or not espaco_ok(fila):
            return
        estado["cancelar"] = False
        barra.config(value=0)
        detalhe.set("")
        travar(True)
        threading.Thread(target=trabalhar, daemon=True,
                         args=(fila, formato.get(), qualidade.get(), pasta_saida.get() or None, dividir.get())).start()

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
