"""Teste rápido: cria um vídeo de 1 minuto com som e converte em todos os formatos/qualidades, com e sem divisão."""
import os
import subprocess
import tempfile

import conversor as c

with tempfile.TemporaryDirectory() as pasta:
    video = os.path.join(pasta, "reunião teste.mp4")
    subprocess.run([c.caminho_ffmpeg(), "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=5",
                    "-f", "lavfi", "-i", "sine=frequency=440", "-t", "60", "-c:v", "mpeg4", "-c:a", "aac",
                    "-b:a", "128k", "-shortest", video], check=True)
    info = c.analisar(video)
    assert abs(info["duracao"] - 60) < 1 and info["codec"] == "aac", info
    for formato, (_, qualidades) in c.FORMATOS.items():
        for q in qualidades:
            saida = c.converter(video, formato, q)
            assert len(saida) == 1 and os.path.getsize(saida[0]) > 10_000, (formato, q, saida)
    assert c.extensao(c.ORIGINAL, info) == "m4a"
    assert info["video"]
    so_audio = c.converter(video, "MP3", next(iter(c.FORMATOS["MP3"][1])))[0]
    try:
        c.converter(so_audio, "WebM — com vídeo (VP9)", next(iter(c.FORMATOS["WebM — com vídeo (VP9)"][1])))
        raise AssertionError("aceitou WebM com vídeo a partir de arquivo sem vídeo")
    except RuntimeError as e:
        assert "não tem vídeo" in str(e)
    assert c.planejar_partes(c.tamanho_estimado_mb("MP3", next(iter(c.FORMATOS["MP3"][1])),
                                                   {**info, "duracao": 3 * 3600}), True) == 1  # 3 h a 128 kbps cabe
    c.LIMITE_MB = 0.4  # força a divisão: 60 s a 128 kbps ≈ 0,94 MB -> 3 partes
    for formato in ("MP3", c.ORIGINAL):
        partes = c.converter(video, formato, next(iter(c.FORMATOS[formato][1])))
        assert len(partes) == 3, (formato, partes)
    n = [0]
    try:
        c.converter(video, "WAV (sem compressão)", next(iter(c.FORMATOS["WAV (sem compressão)"][1])),
                    cancelado=lambda: n.__setitem__(0, n[0] + 1) or n[0] > 2)
        raise AssertionError("não cancelou")
    except InterruptedError:
        pass
    assert [f for f in os.listdir(pasta) if f.endswith(".wav")] == ["reunião teste.wav"], "cancelamento deixou arquivo"
print("ok")
