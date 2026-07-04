#!/usr/bin/env python3
# 👤 =====================================================================
# 👤 SILO DIARIZAR (#77) — estima cuántos HABLANTES hay en un audio.
# 👤 Usa resemblyzer (los mismos embeddings de tu compara_voces) + clustering
# 👤 aglomerativo eligiendo k por silhouette. Imprime UN entero:
# 👤   0 = no disponible (faltan libs / audio) · 1+ = nº estimado de hablantes.
# 👤 Degrada con elegancia: nunca lanza excepción al llamador.
# 👤 Uso:  python3 silo_diarizar.py audio.wav        (DIAR_PY = python del entorno con resemblyzer)
# 👤 =====================================================================
import sys


def contar(audio):
    try:
        from pathlib import Path
        import numpy as np
        from resemblyzer import VoiceEncoder, preprocess_wav
        wav = preprocess_wav(Path(audio))
        enc = VoiceEncoder(verbose=False)
        _, partials, _ = enc.embed_utterance(wav, return_partials=True, rate=1.3)
        X = np.array(partials)
        if len(X) < 4:
            return 1                                   # muy corto → 1 hablante
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.metrics import silhouette_score
        mejor_k, mejor_s = 1, -1.0
        for k in range(2, min(7, len(X))):
            etiquetas = AgglomerativeClustering(n_clusters=k).fit_predict(X)
            try:
                s = silhouette_score(X, etiquetas)
            except Exception:
                s = -1.0
            if s > mejor_s:
                mejor_s, mejor_k = s, k
        # silueta pobre = no hay separación clara → probablemente 1 voz
        return mejor_k if mejor_s > 0.10 else 1
    except Exception as e:
        print(f"diar no disponible: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    print(contar(sys.argv[1]) if len(sys.argv) > 1 else 0)
