"""Teste rápido: cria um vídeo de 1 minuto com som, converte em todos os formatos e testa a divisão."""
import os
import subprocess
import tempfile

import conversor as c

with tempfile.TemporaryDirectory() as pasta:
    video = os.path.join(pasta, "reunião teste.mp4")
    subprocess.run([c.caminho_ffmpeg(), "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=5",
                    "-f", "lavfi", "-i", "sine=frequency=440", "-t", "60", "-c:v", "mpeg4", "-c:a", "aac",
                    "-shortest", video], check=True)
    assert abs(c.duracao_segundos(c.caminho_ffmpeg(), video) - 60) < 1
    for formato in c.FORMATOS:
        saida = c.converter(video, formato)
        assert len(saida) == 1 and os.path.getsize(saida[0]) > 10_000, (formato, saida)
    assert c.planejar_partes(4 * 3600, 64, True) == 1  # reunião de 4 h cabe num arquivo só
    c.LIMITE_MB = 0.2  # força a divisão: 60 s a 64 kbps ≈ 0,47 MB -> 3 partes
    partes = c.converter(video, c.FORMATO_PADRAO)
    assert len(partes) == 3, partes
print("ok")
