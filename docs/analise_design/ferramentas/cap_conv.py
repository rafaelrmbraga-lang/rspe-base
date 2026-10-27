import os
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
import os, sys, subprocess, threading, time as _t
SP = os.environ.get("APTO_TRABALHO", os.path.join(__import__("tempfile").gettempdir(), "apto_analise"))
OUT = os.path.join(REPO, "docs", "analise_design", "capturas")
sys.path.insert(0, SP + "/conv")
import conversor as C
import tkinter as tk
from tkinter import ttk, filedialog

MODO = sys.argv[1]
# arquivos fictícios (esparsos)
os.makedirs(SP + "/videos", exist_ok=True)
F1 = SP + "/videos/reuniao_ficticia_mutirao_2026-10-15.mp4"
F2 = SP + "/videos/audiencia_ficticia_02.mkv"
for f, sz in ((F1, 3_400_000_000), (F2, 900_000_000)):
    with open(f, "wb") as h: h.truncate(sz)

INFO = {F1: {"duracao": 3 * 3600 + 12 * 60, "codec": "aac", "kbps": 128, "hz": 48000, "canais": 2, "video": True},
        F2: {"duracao": 47 * 60, "codec": "aac", "kbps": 96, "hz": 44100, "canais": 2, "video": True}}
C.analisar = lambda f, ff=None: (_t.sleep(0.2), INFO[f])[1]
filedialog.askopenfilenames = lambda **k: [F1, F2]

class Relogio:
    v = 0.0
    @staticmethod
    def monotonic(): return Relogio.v
C.time = Relogio

ROOT = {}
_Tk = tk.Tk
def Tk(*a, **k):
    r = _Tk(*a, **k); ROOT["r"] = r; r.after(800, roteiro); return r
tk.Tk = Tk

def todos(w):
    yield w
    for c in w.winfo_children(): yield from todos(c)
def botao(txt):
    return next(w for w in todos(ROOT["r"]) if isinstance(w, ttk.Button) and str(w.cget("text")) == txt)
def combos():
    return [w for w in todos(ROOT["r"]) if isinstance(w, ttk.Combobox)]

def foto(nome, janela=True):
    r = ROOT["r"]; r.update(); _t.sleep(0.3); r.update()
    p = f"{OUT}/conversor_{nome}.png"
    if janela:
        x, y, w, h = r.winfo_rootx(), r.winfo_rooty(), r.winfo_width(), r.winfo_height()
        subprocess.run(["import", "-window", "root", "-crop", f"{w}x{h}+{x}+{y}", p])
    else:
        subprocess.run(["import", "-window", "root", "-crop", "1000x760+0+0", p])

def fake_converter(arq, fmt, q, pasta, div, prog, cancelado, info):
    # simula ffmpeg: passos com relógio controlado
    dur = info["duracao"]
    lento = "VP9" in fmt
    vel = 0.45 if lento else 40.0
    for fr in (0.05, 0.2, 0.37):
        Relogio.v = fr * dur / vel
        prog(fr); _t.sleep(0.3)
        if cancelado(): raise InterruptedError("Conversão cancelada.")
    EV.wait(20)
    if cancelado(): raise InterruptedError("Conversão cancelada.")
    if MODO == "erro":
        raise RuntimeError("[aac @ 0x55d0c8a4e2c0] Error while decoding stream #0:1: Invalid data found when processing input\n"
                           "Error submitting packet to decoder: Invalid data found when processing input\n"
                           "[out#0/mp3 @ 0x55d0c8a5f400] Error muxing a packet\nConversion failed!")
    out = os.path.splitext(arq)[0] + ".mp3"
    with open(out, "wb") as h: h.truncate(int(info["duracao"] * 128 / 8 * 1000))
    return [out]
C.converter = fake_converter
EV = threading.Event()

def roteiro():
    r = ROOT["r"]
    if MODO == "inicial":
        foto("inicial"); r.destroy(); return
    if MODO == "minimo":
        r.geometry("580x560"); r.update(); botao("Escolher…").invoke(); r.after(1200, lambda: (foto("tamanho_minimo_580x560"), r.destroy())); return
    botao("Escolher…").invoke()
    def depois_ler():
        if MODO == "arquivos":
            foto("arquivos_mp3"); r.destroy(); return
        if MODO in ("webm_video", "lento"):
            cf, cq = combos()
            cf.set("WebM — com vídeo (VP9)"); cf.event_generate("<<ComboboxSelected>>"); r.update()
            if MODO == "webm_video":
                foto("formato_webm_video"); r.destroy(); return
        botao("Converter").invoke()
        def durante():
            foto("convertendo_lento_vp9" if MODO == "lento" else "convertendo")
            if MODO == "cancelar":
                botao("Cancelar").invoke(); r.update(); foto("cancelando"); EV.set()
                r.after(1500, lambda: (foto("cancelado"), r.destroy()))
                return
            if MODO == "lento":
                r.destroy(); os._exit(0)
            EV.set()
            r.after(1500, lambda: foto("concluido" if MODO == "fim" else "erro", janela=False))
            r.after(2500, lambda: os._exit(0))
        r.after(1800, durante)
    r.after(1200, depois_ler)

C.app()
