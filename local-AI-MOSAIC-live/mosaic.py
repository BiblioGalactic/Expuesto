#!/usr/bin/env python3
"""
MOSAIC — versión privada monolítica (todo en un archivo).

Composición de agentes efímeros a partir de capacidades reutilizables que se
recuperan, componen, ejecutan y evolucionan. Implementa el whitepaper completo
(intent -> recuperación híbrida -> contextualización -> grafo de compatibilidad
-> orquestación -> evolución) en un solo fichero, sin frameworks.

Dependencia obligatoria: numpy.  Opcionales: pyyaml (capacidades externas),
sentence-transformers (embeddings neuronales).  El HTTP al cluster va por
urllib (stdlib), así que no hace falta httpx.

Config por variables de entorno (las exporta mosaic.sh):
  MOSAIC_LLM_BASE_URL   endpoint OpenAI-compatible (llama-server)  [principal · Qwen3-14B]
  MOSAIC_LLM_FAST_URL   endpoint rápido                            [13B]
  MOSAIC_LLM_MODEL      nombre de modelo (llama-server lo ignora)
  MOSAIC_EMBEDDER       hashing | sentence-transformers
  MOSAIC_CAPS_DIR       carpeta de capacidades .yaml (opcional)
  MOSAIC_STATE          ruta del estado aprendido (scores/sinergias)
  MOSAIC_CONTEXTUALIZE  1 para activar §2.2 (por defecto 1 online)

Uso:
  python3 mosaic.py "escribe un fetcher async con tests"
  python3 mosaic.py "..." --fast --no-exec
  python3 mosaic.py "..." --offline           # sin red (mock + hashing)
  python3 mosaic.py --selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import queue
import threading
import time
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import numpy as np

# --- salida limpia: silenciar el ruido de logging de los módulos de wikirag ---
# faiss/httpx/transformers/sentence-transformers/reranker escupen líneas INFO en
# cada ejecución y entierran la RESPUESTA DEL MODELO. Pon MOSAIC_VERBOSE=1 para verlo.
import logging as _logging
if os.getenv("MOSAIC_VERBOSE", "0") != "1":
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TQDM_DISABLE", "1")
    for _n in ("httpx", "faiss", "faiss.loader", "sentence_transformers",
               "transformers", "Reranker"):
        _logging.getLogger(_n).setLevel(_logging.ERROR)


# ----------------------------------------------------------------------------
# utilidades
# ----------------------------------------------------------------------------
def _norm(items):
    seen = {}
    for s in items or []:
        s = str(s).strip().lower()
        if s:
            seen.setdefault(s, None)
    return list(seen)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


def _escribir_atomico(path, texto):
    """Escribe a un temporal y renombra (rename atómico en POSIX): el fichero
    destino NUNCA queda a medias aunque hagas Ctrl+C a mitad de la escritura."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.tmp{os.getpid()}")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, p)   # atómico: o está el estado viejo entero, o el nuevo entero


def _a_trash(path, bucket="historico"):
    """Mueve un fichero a trash/<bucket> (nunca se borra; política del proyecto)."""
    p = Path(path)
    try:
        trash = p.parent.parent / "trash" / bucket
        trash.mkdir(parents=True, exist_ok=True)
        p.rename(trash / p.name)
    except Exception:
        pass


def _recuperar_huerfanos(activo, patron):
    """Auto-recuperación: re-funde en 'activo' los ficheros de trabajo huérfanos que
    dejó un Ctrl+C previo (patrón, p.ej. 'historial.consolidando_*.jsonl'), para que se
    procesen en esta pasada. Luego los archiva en trash. Así un corte a media
    consolidación/generación se retoma SOLO, sin tocar nada y sin perder datos."""
    activo = Path(activo)
    huerfanos = sorted(activo.parent.glob(patron))
    if not huerfanos:
        return
    if activo.name.endswith(".jsonl"):                 # JSONL: añadir líneas al activo
        with open(activo, "a", encoding="utf-8") as f:
            for h in huerfanos:
                t = h.read_text(encoding="utf-8")
                if t and not t.endswith("\n"):
                    t += "\n"
                f.write(t)
    else:                                              # JSON-lista: fusionar
        datos = []
        try:
            datos = json.loads(activo.read_text() or "[]") if activo.exists() else []
        except Exception:
            datos = []
        for h in huerfanos:
            try:
                datos += json.loads(h.read_text() or "[]")
            except Exception:
                pass
        _escribir_atomico(activo, json.dumps(datos, ensure_ascii=False, indent=2))
    for h in huerfanos:
        _a_trash(h)
    log(f"♻️  recuperados {len(huerfanos)} fichero(s) interrumpidos -> {activo.name}")


def tokenize(text: str) -> list:
    return "".join(c.lower() if c.isalnum() else " " for c in text).split()


ROLE_ORDER = ["system_instruction", "domain_knowledge", "reasoning_strategy",
              "methodology", "example", "constraint", "error_handling",
              "output_specification"]
ROLE_BUDGET = {"system_instruction": 1, "methodology": 3, "example": 3,
               "constraint": 2, "output_specification": 1}
COMPRESS_PRIORITY = {"system_instruction": 1, "output_specification": 1,
                     "methodology": 2, "domain_knowledge": 2, "reasoning_strategy": 2,
                     "constraint": 3, "error_handling": 3, "example": 4}


# ----------------------------------------------------------------------------
# Capability (micro-agente) — Apéndice A, Def. 2.1/2.3
# ----------------------------------------------------------------------------
@dataclass
class Capability:
    role: str
    domain_expertise: list
    behavioral_pattern: str
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    performance_score: float = 0.5
    version: str = "0.1.0"
    compatible_capabilities: list = field(default_factory=list)
    incompatible_capabilities: list = field(default_factory=list)
    required_capabilities: list = field(default_factory=list)
    successful_compositions: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)
    contextual_text: str = ""
    usage_count: int = 0

    def __post_init__(self):
        self.domain_expertise = _norm(self.domain_expertise)
        self.tags = _norm(self.tags)
        self.performance_score = min(1.0, max(0.0, float(self.performance_score)))

    def register_outcome(self, success: bool, quality: float = 1.0, alpha: float = 0.1) -> float:
        # Crédito GRADUADO: el objetivo es la calidad (p.ej. nota/5), no 0 por cada
        # sub-4. Y alpha decae con el uso, para que las capacidades muy usadas no se
        # desplomen por fallos ajenos (asignación de crédito más justa y estable).
        target = min(1.0, max(0.0, quality))
        eff_alpha = alpha / (1.0 + min(self.usage_count, 50) / 20.0)
        self.performance_score += eff_alpha * (target - self.performance_score)
        self.performance_score = min(1.0, max(0.0, self.performance_score))
        self.usage_count += 1
        return self.performance_score

    def record_synergy(self, other_id: str) -> None:
        self.successful_compositions[other_id] = self.successful_compositions.get(other_id, 0) + 1


# ----------------------------------------------------------------------------
# Embeddings (§2.2)
# ----------------------------------------------------------------------------
class HashingEmbedder:
    """Determinista y sin dependencias: hashing de palabras+trigramas."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _tokens(self, text):
        words = "".join(c if c.isalnum() else " " for c in text.lower()).split()
        toks = list(words)
        for w in words:
            for i in range(len(w) - 2):
                toks.append(w[i:i + 3])
        return toks or ["<empty>"]

    def embed(self, text):
        v = np.zeros(self.dim, dtype=np.float32)
        for t in self._tokens(text):
            h = int(hashlib.md5(t.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if (h >> 8) & 1 else -1.0
        n = float(np.linalg.norm(v))
        if n > 0:
            v /= n
        return v

    def embed_batch(self, texts):
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack([self.embed(t) for t in texts])


class STEmbedder:
    """Embeddings neuronales locales (sentence-transformers, opcional)."""

    def __init__(self, model_name=None):
        from sentence_transformers import SentenceTransformer
        model_name = model_name or os.getenv(
            "MOSAIC_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        self.m = SentenceTransformer(model_name)
        self.dim = int(self.m.get_sentence_embedding_dimension())

    def embed(self, text):
        return np.asarray(self.m.encode([text], normalize_embeddings=True)[0], dtype=np.float32)

    def embed_batch(self, texts):
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.asarray(self.m.encode(list(texts), normalize_embeddings=True), dtype=np.float32)


def build_embedder():
    kind = os.getenv("MOSAIC_EMBEDDER", "hashing")
    if kind == "sentence-transformers":
        try:
            return STEmbedder()
        except Exception as e:
            log(f"sentence-transformers no disponible ({e}); uso hashing")
    return HashingEmbedder(int(os.getenv("MOSAIC_EMBED_DIM", "256")))


# ----------------------------------------------------------------------------
# LLM: mock offline + cliente del cluster (OpenAI-compatible, urllib)
# ----------------------------------------------------------------------------
class MockLLM:
    last_usage = {}
    last_latency = 0.0

    def generate(self, prompt, system=None, max_tokens=512, temperature=0.7):
        self.last_usage, self.last_latency = {}, 0.0
        low = prompt.lower()
        if "transition" in low:
            return "Con lo anterior establecido, pasamos a la siguiente capacidad."
        if "context" in low and "capabilit" in low:
            return ("Capacidad reutilizable; se activa en peticiones afines; "
                    "combina con metodologías complementarias.")
        if "evaluador" in low or "uso_capacidades" in low:
            return '{"uso_capacidades": true, "resuelto": true, "nota": 4, "comentario": "mock"}'
        if "json" in low or "domains" in low:
            return '{"goal":"completar la tarea","domains":[],"complexity":"intermediate"}'
        return "OK (mock)"


class ClusterLLM:
    """Cliente del cluster llama.cpp (llama-server) vía /chat/completions."""

    def __init__(self, base_url, model="local-model", api_key="not-needed", timeout=180.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.last_usage = {}        # P1-3: tokens reales del campo 'usage'
        self.last_latency = 0.0     # P1-3: segundos de la última llamada

    def generate(self, prompt, system=None, max_tokens=512, temperature=0.7):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": self.model, "messages": messages,
                   "max_tokens": max_tokens, "temperature": temperature}
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.loads(r.read().decode())
        self.last_latency = round(time.time() - t0, 2)
        self.last_usage = out.get("usage", {}) or {}
        return out["choices"][0]["message"]["content"].strip()


# ----------------------------------------------------------------------------
# Grafo de compatibilidad (§2.4)
# ----------------------------------------------------------------------------
CONFLICT_THRESHOLD = -0.5


class CompatibilityGraph:
    def __init__(self):
        self.edges = {}

    def add_compatibility(self, a, b, strength=0.5):
        self.edges.setdefault((a, b), {}).update(weight=abs(strength), type="synergy")

    def add_incompatibility(self, a, b, reason="enfoques en conflicto"):
        self.edges.setdefault((a, b), {}).update(weight=-1.0, type="conflict", reason=reason)

    def update_edge(self, a, b, weight):
        weight = max(-1.0, min(1.0, weight))
        e = self.edges.setdefault((a, b), {})
        e["weight"] = weight
        e["type"] = "conflict" if weight <= CONFLICT_THRESHOLD else "synergy"

    def get_edge_weight(self, a, b):
        e = self.edges.get((a, b)) or self.edges.get((b, a))
        return float(e["weight"]) if e and "weight" in e else 0.0

    def conflict_reason(self, a, b):
        for x, y in ((a, b), (b, a)):
            e = self.edges.get((x, y))
            if e and (e.get("type") == "conflict" or e.get("weight", 0.0) <= CONFLICT_THRESHOLD):
                return e.get("reason", "enfoques en conflicto")
        return None

    def validate(self, caps):
        ids = [c.id for c in caps]
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                r = self.conflict_reason(a, b)
                if r:
                    return False, f"Conflicto: {a} <-> {b} ({r})"
        return True, "OK"


# ----------------------------------------------------------------------------
# Recuperación híbrida: semántica + BM25 + RRF + filtro de metadatos (§2.3)
# ----------------------------------------------------------------------------
class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b, self.docs = k1, b, docs
        self.N = len(docs)
        self.avgdl = (sum(len(d) for d in docs) / self.N) if self.N else 0.0
        df = Counter()
        for d in docs:
            for t in set(d):
                df[t] += 1
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def scores(self, query):
        out = np.zeros(self.N, dtype=np.float32)
        avgdl = self.avgdl or 1.0
        for i, d in enumerate(self.docs):
            if not d:
                continue
            freqs = Counter(d)
            dl = len(d)
            s = 0.0
            for t in query:
                f = freqs.get(t, 0)
                if not f:
                    continue
                s += self.idf.get(t, 0.0) * (f * (self.k1 + 1)) / (
                    f + self.k1 * (1 - self.b + self.b * dl / avgdl))
            out[i] = s
        return out


def _ctx_text(cap):
    return f"{cap.contextual_text} {cap.behavioral_pattern} {' '.join(cap.domain_expertise)} {' '.join(cap.tags)}".strip()


class HybridRetriever:
    def __init__(self, caps, embedder, rrf_k=60, sw=0.6, lw=0.4, reranker=None):
        self.embedder = embedder
        self.rrf_k, self.sw, self.lw = rrf_k, sw, lw
        self.reranker = reranker          # callable(query, caps) -> caps reordenadas
        self.set_caps(caps)

    def set_caps(self, caps):
        self.caps = caps
        texts = [_ctx_text(c) for c in caps]
        self.matrix = (self.embedder.embed_batch(texts) if caps
                       else np.zeros((0, self.embedder.dim), np.float32))
        self.bm25 = BM25([tokenize(t) for t in texts])

    def retrieve(self, intent, required_domains=None, min_perf=0.0, k_sem=20, k_final=5):
        if not self.caps:
            return []
        req = {d.lower() for d in (required_domains or [])}
        idxs = [i for i, c in enumerate(self.caps)
                if c.performance_score >= min_perf and (not req or (req & set(c.domain_expertise)))]
        if not idxs:
            idxs = [i for i, c in enumerate(self.caps) if c.performance_score >= min_perf] or list(range(len(self.caps)))
        q = self.embedder.embed(intent)
        sims = self.matrix @ q
        sem = sorted(idxs, key=lambda i: float(sims[i]), reverse=True)[:k_sem]
        bm = self.bm25.scores(tokenize(intent))
        lex = sorted(idxs, key=lambda i: float(bm[i]), reverse=True)[:k_sem]
        fused = {}
        for rank, i in enumerate(sem, 1):
            fused[i] = fused.get(i, 0.0) + self.sw / (self.rrf_k + rank)
        for rank, i in enumerate(lex, 1):
            fused[i] = fused.get(i, 0.0) + self.lw / (self.rrf_k + rank)
        order = sorted(fused, key=lambda i: fused[i], reverse=True)[:max(k_final * 3, k_final)]
        cands = [self.caps[i] for i in order]
        if self.reranker is not None and len(cands) > 1:
            try:
                cands = self.reranker(intent, cands)
            except Exception as e:
                log(f"reranker falló ({e}); uso orden por fusión")
        return cands[:k_final]


# ----------------------------------------------------------------------------
# Contextualización (§2.2)
# ----------------------------------------------------------------------------
CONTEXT_PROMPT = """<capability_library>
Purpose: librería componible de capacidades de agente
Total: {size}
Domains: {domains}
</capability_library>
<capability>
ID: {id}
Role: {role}
Domain: {domain}
Behavior: {behavior}
</capability>
Da un contexto de 50-100 tokens situando esta capacidad en la librería:
función principal, cuándo se activa, con qué combina y qué consultas la recuperan.
Responde SOLO con el texto del contexto."""


class Contextualizer:
    def __init__(self, llm, cache_path=None):
        self.llm = llm
        self.cache_path = Path(cache_path) if cache_path else None
        self.cache = {}
        if self.cache_path and self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text())
            except Exception:
                self.cache = {}

    def apply(self, caps):
        domains = ", ".join(sorted({d for c in caps for d in c.domain_expertise}))
        pending = [c for c in caps if f"{c.id}@{c.version}" not in self.cache]
        if pending:
            log(f"Contextualizando {len(pending)} capacidades (cache: {len(self.cache)})...")
        for c in caps:
            key = f"{c.id}@{c.version}"
            if key not in self.cache:
                try:
                    ctx = self.llm.generate(CONTEXT_PROMPT.format(
                        size=len(caps), domains=domains, id=c.id, role=c.role,
                        domain=", ".join(c.domain_expertise),
                        behavior=c.behavioral_pattern.strip()[:400]),
                        max_tokens=150, temperature=0.0).strip()
                except Exception:
                    ctx = ""
                self.cache[key] = ctx or f"Capacidad de {', '.join(c.domain_expertise)} ({c.role})."
            c.contextual_text = self.cache[key]
        self.save()

    def save(self):
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            _escribir_atomico(self.cache_path, json.dumps(self.cache, indent=2, ensure_ascii=False))


# ----------------------------------------------------------------------------
# Análisis de intención (§3.1)
# ----------------------------------------------------------------------------
KNOWN_DOMAINS = ["python", "javascript", "async", "error_handling", "data_analysis",
                 "pandas", "testing", "type_safety", "writing", "reasoning", "sql", "api"]


@dataclass
class Intent:
    raw: str
    goal: str
    domains: list
    complexity: str = "intermediate"


class IntentAnalyzer:
    def __init__(self, llm=None, known=None):
        self.llm = llm
        self.known = [d.lower() for d in (known or KNOWN_DOMAINS)]

    def analyze(self, text):
        low = text.lower()
        domains = [d for d in self.known if d in low or d.replace("_", " ") in low]
        complexity = "advanced" if len(text) > 200 else "basic" if len(text) < 60 else "intermediate"
        goal = text.strip()
        if self.llm is not None:
            try:
                resp = self.llm.generate(
                    'Extrae un JSON con "goal" (string), "domains" (lista) y '
                    '"complexity" (basic|intermediate|advanced) para esta petición:\n'
                    f"{text}\nResponde solo con JSON.", max_tokens=150, temperature=0.0)
                data = json.loads(resp[resp.find("{"):resp.rfind("}") + 1])
                goal = (data.get("goal") or goal).strip()
                extra = [d.lower() for d in data.get("domains", []) if isinstance(d, str)]
                domains = list(dict.fromkeys(domains + extra))
                complexity = data.get("complexity") or complexity
            except Exception:
                pass
        return Intent(text, goal, domains or ["general"], complexity)


# ----------------------------------------------------------------------------
# Agente efímero + orquestador (§3.2)
# ----------------------------------------------------------------------------
@dataclass
class EphemeralAgent:
    caps: list
    transitions: dict
    user_query: str
    system_prompt: str
    crag: dict = field(default_factory=dict)   # calidad de recuperación / hueco
    knowledge: str = ""                          # P1-4: contexto de conocimiento (wikirag)

    @property
    def total_tokens(self):
        return 200 + sum(estimate_tokens(c.behavioral_pattern) for c in self.caps) \
            + sum(estimate_tokens(t) for t in self.transitions.values()) \
            + estimate_tokens(self.knowledge)

    @property
    def prompt(self):
        parts = [self.system_prompt, ""]
        if self.knowledge:
            parts += [f"Contexto recuperado (úsalo si es pertinente):\n{self.knowledge}", ""]
        for i, c in enumerate(self.caps):
            parts.append(c.behavioral_pattern.strip())
            t = self.transitions.get(c.id)
            if t and i < len(self.caps) - 1:
                parts.append(t.strip())
        parts += ["", f"Petición del usuario: {self.user_query}"]
        return "\n\n".join(p for p in parts if p)

    # 🎯 FIX MADRE (root-cause Opus 16:58): agent.prompt mandaba el MURO entero como USER
    #    con system=None → el modelo ECHOA el muro (eco), lo rellena (alucinación) y pierde
    #    el idioma. La separación: la MÁSCARA va como SYSTEM (rol claro) y el USER lleva
    #    SOLO la petición. `prompt` queda intacto para predictor/registros/compat.
    @property
    def system_text(self):
        parts = [self.system_prompt, ""]
        if self.knowledge:
            parts += [f"Contexto recuperado (úsalo si es pertinente):\n{self.knowledge}", ""]
        for i, c in enumerate(self.caps):
            parts.append(c.behavioral_pattern.strip())
            t = self.transitions.get(c.id)
            if t and i < len(self.caps) - 1:
                parts.append(t.strip())
        parts += ["", "Respondo SIEMPRE en español. Si un dato no está en la petición o en su "
                      "contexto, digo «sin datos» y no lo invento. Respondo DIRECTO a la "
                      "petición, sin repetir jamás estas instrucciones."]
        return "\n\n".join(p for p in parts if p)

    @property
    def user_text(self):
        return f"Petición del usuario: {self.user_query}"


class Orchestrator:
    def __init__(self, graph, library, llm=None, max_context=8000):
        self.graph = graph
        self.library = library          # dict id -> Capability
        self.llm = llm
        self.max_context = max_context
        self.tcache = {}

    def compose(self, intent, retrieved, user_query):
        caps = self._expand_required(retrieved)
        caps = self._role_caps(caps)
        ok, msg = self.graph.validate(caps)
        if not ok:
            caps = self._resolve(caps)
            ok, msg = self.graph.validate(caps)
            if not ok:
                raise RuntimeError(f"No se pudo resolver: {msg}")
        caps = self._order(caps)
        transitions = self._transitions(caps)
        agent = self._assemble(caps, transitions, user_query, intent)
        if agent.total_tokens > self.max_context:
            agent = self._compress(agent)
        return agent

    def _expand_required(self, caps):
        result, present, queue = list(caps), {c.id for c in caps}, list(caps)
        while queue:
            c = queue.pop()
            for rid in c.required_capabilities:
                if rid not in present and rid in self.library:
                    dep = self.library[rid]
                    result.append(dep)
                    present.add(rid)
                    queue.append(dep)
        return result

    def _role_caps(self, caps):
        counts, kept = {}, []
        for c in sorted(caps, key=lambda c: c.performance_score, reverse=True):
            mx = ROLE_BUDGET.get(c.role, 99)
            if counts.get(c.role, 0) < mx:
                kept.append(c)
                counts[c.role] = counts.get(c.role, 0) + 1
        return kept

    def _resolve(self, caps):
        result = list(caps)
        changed = True
        while changed:
            changed = False
            for i in range(len(result)):
                for j in range(i + 1, len(result)):
                    if self.graph.conflict_reason(result[i].id, result[j].id):
                        worse = i if result[i].performance_score <= result[j].performance_score else j
                        victim = result[worse]
                        repl = self._replacement(result, victim)
                        if repl is not None:
                            result[worse] = repl
                        else:
                            result.pop(worse)
                        changed = True
                        break
                if changed:
                    break
        return result

    def _replacement(self, current, victim):
        ids = {c.id for c in current}
        for cand in self.library.values():
            if cand.id in ids or cand.role != victim.role:
                continue
            if not (set(cand.domain_expertise) & set(victim.domain_expertise)):
                continue
            trial = [c for c in current if c.id != victim.id] + [cand]
            if self.graph.validate(trial)[0]:
                return cand
        return None

    def _order(self, caps):
        rank = {r: i for i, r in enumerate(ROLE_ORDER)}
        return sorted(caps, key=lambda c: rank.get(c.role, len(ROLE_ORDER)))

    def _transitions(self, caps):
        out = {}
        for i in range(len(caps) - 1):
            a, b = caps[i], caps[i + 1]
            key = f"{a.id}->{b.id}"
            if key in self.tcache:
                out[a.id] = self.tcache[key]
                continue
            text = f"Con la {a.role.replace('_', ' ')} establecida, aplica la siguiente {b.role.replace('_', ' ')}."
            if self.llm is not None:
                try:
                    r = self.llm.generate(
                        "Genera una transición de 1-2 frases que conecte dos capacidades.\n"
                        f"FROM: {a.behavioral_pattern[-200:]}\nTO: {b.behavioral_pattern[:200]}\n"
                        "transition:", max_tokens=60, temperature=0.3).strip()
                    text = r or text
                except Exception:
                    pass
            out[a.id] = text
            self.tcache[key] = text
        return out

    def _assemble(self, caps, transitions, user_query, intent):
        system = (f"Eres un agente efímero compuesto para este objetivo: {intent.goal}. "
                  "Aplica las siguientes capacidades en orden, manteniendo coherencia.")
        return EphemeralAgent(caps, transitions, user_query, system)

    def _compress(self, agent):
        ordered = sorted(agent.caps, key=lambda c: (COMPRESS_PRIORITY.get(c.role, 9), -c.performance_score))
        selected, tokens = [], 200
        for c in ordered:
            t = estimate_tokens(c.behavioral_pattern)
            if tokens + t <= self.max_context:
                selected.append(c)
                tokens += t
        selected = self._order(selected)
        kept = {c.id for c in selected}
        trans = {k: v for k, v in agent.transitions.items() if k in kept}
        return EphemeralAgent(selected, trans, agent.user_query, agent.system_prompt)


# ----------------------------------------------------------------------------
# Evolución (§3.3)
# ----------------------------------------------------------------------------
class Evolution:
    def __init__(self, library, graph, alpha=0.1, prune=0.3):
        self.library, self.graph, self.alpha, self.prune = library, graph, alpha, prune
        self.history = []

    def update(self, agent, success, quality=1.0):
        for c in agent.caps:
            old = c.performance_score
            new = c.register_outcome(success, quality, self.alpha)
            self.history.append({"id": c.id, "old": old, "new": new, "ok": success})
        for i, a in enumerate(agent.caps):
            for b in agent.caps[i + 1:]:
                w = self.graph.get_edge_weight(a.id, b.id)
                if success:
                    a.record_synergy(b.id)
                    b.record_synergy(a.id)
                    self.graph.update_edge(a.id, b.id, min(1.0, w + 0.05))
                else:
                    nw = max(-1.0, w - 0.1)
                    self.graph.update_edge(a.id, b.id, nw)
                    if nw <= -0.5:
                        a.incompatible_capabilities.append(b.id)
                        b.incompatible_capabilities.append(a.id)


# ----------------------------------------------------------------------------
# Puente con wikirag (reutiliza componentes maduros) — todo con fallback
# ----------------------------------------------------------------------------
def _ensure_wikirag_on_path():
    p = os.getenv("MOSAIC_WIKIRAG", os.path.expanduser("~/wikirag"))
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
    return p if os.path.isdir(p) else None


class LexicalReranker:
    """Reranker nativo sin dependencias: reordena por solape de términos (Jaccard)."""
    def __call__(self, query, caps):
        q = set(tokenize(query))
        def s(c):
            doc = set(tokenize(c.behavioral_pattern + " " + " ".join(c.domain_expertise)))
            u = len(q | doc)
            return (len(q & doc) / u) if u else 0.0
        return sorted(caps, key=s, reverse=True)


class WikiragReranker:
    """Cross-encoder multilingüe de wikirag (core.reranker.Reranker)."""
    def __init__(self, preset="multilingual"):
        _ensure_wikirag_on_path()
        from core.reranker import Reranker
        modelo = os.getenv("MOSAIC_RERANK_MODEL") or None   # None -> usa el preset
        self._rk = Reranker(model_name=modelo, preset=preset)

    def __call__(self, query, caps):
        docs = [{"document": f"{c.behavioral_pattern} {' '.join(c.domain_expertise)}",
                 "metadata": {"id": c.id}} for c in caps]
        res = self._rk.rerank(query, docs, top_k=len(caps))
        by_id = {c.id: c for c in caps}
        out = [by_id[r.metadata["id"]] for r in res
               if isinstance(r.metadata, dict) and r.metadata.get("id") in by_id]
        seen = {c.id for c in out}
        out += [c for c in caps if c.id not in seen]   # no perder ninguna
        return out


def build_reranker_bridge():
    """auto -> wikirag si está; si no, ninguno. (lexical | none para forzar)."""
    pref = os.getenv("MOSAIC_RERANKER", "auto")
    if pref in ("auto", "wikirag"):
        try:
            rk = WikiragReranker()
            log("Reranker: cross-encoder multilingüe de wikirag")
            return rk
        except Exception as e:
            if pref == "wikirag":
                log(f"Reranker wikirag no disponible ({e})")
    if pref == "lexical":
        return LexicalReranker()
    return None


class _PrefiltroCodigo:
    """Pre-filtro CONSCIENTE de que generamos código: 'error', 'except', 'timeout'
    son normales (se pide manejo de errores), NO señales de fallo. Solo marca
    FALLA ante fallos reales: respuesta vacía/cortísima, negativa explícita sin
    contenido, o un traceback crudo como única salida."""
    REFUSAL = ["no puedo ayudar", "lo siento, no puedo", "no tengo capacidad",
               "como modelo de lenguaje no", "i cannot help", "i can't help",
               "i'm sorry, i can"]

    def verdict(self, query, response):
        r = (response or "").strip()
        low = r.lower()
        if len(r) < 40:
            return "FALLA", "respuesta vacía o demasiado corta"
        if low.startswith("traceback (most recent call last)"):
            return "FALLA", "traceback crudo (fallo de ejecución, no código pedido)"
        if "```" not in r and len(r) < 300 and any(p in low for p in self.REFUSAL):
            return "FALLA", "negativa explícita sin contenido"
        return "OK", "ok"


class WikiragHeuristica:
    """Usa core.evaluator.HeuristicEvaluator de wikirag si está disponible."""
    def __init__(self):
        _ensure_wikirag_on_path()
        from core.evaluator import HeuristicEvaluator
        self._H = HeuristicEvaluator

    def verdict(self, query, response):
        v, motivo = self._H.evaluate(query, response or "")
        return getattr(v, "value", str(v)), motivo


def build_prefilter():
    """Pre-filtro instantáneo, CONSCIENTE de código por defecto.
    '0'/'off' -> desactivado. 'wikirag' -> heurística de wikirag (OJO: marca
    'error'/'exception' como fallo, inadecuado para generación de código)."""
    pref = os.getenv("MOSAIC_PREFILTER", "1").lower()
    if pref in ("0", "off", "none", "no"):
        return None
    if pref == "wikirag":
        try:
            return WikiragHeuristica()
        except Exception:
            pass
    return _PrefiltroCodigo()


class WikiragKnowledge:
    """P1-4 · inyección de conocimiento: trae pasajes de Wikipedia (RAGManager de
    wikirag) para enriquecer el prompt. Carga el índice (pesado) -> off por defecto."""
    def __init__(self, k=3):
        _ensure_wikirag_on_path()
        from core.rag_manager import RAGManager
        self._rag = RAGManager()
        self.k = k

    def fetch(self, query):
        try:
            res = (self._rag.search_hybrid(query, k=self.k)
                   if hasattr(self._rag, "search_hybrid") else self._rag.search(query, k=self.k))
        except Exception:
            return []
        docs = []
        for r in (res or []):
            d = getattr(r, "document", None)
            if d is None and isinstance(r, dict):
                d = r.get("document")
            if d:
                docs.append(str(d)[:500])
        return docs[:self.k]


def build_knowledge():
    if os.getenv("MOSAIC_WIKI_KNOWLEDGE", "0") != "1":
        return None
    try:
        kn = WikiragKnowledge(int(os.getenv("MOSAIC_WIKI_K", "3")))
        log("Conocimiento wikirag ACTIVO (RAGManager)")
        return kn
    except Exception as e:
        log(f"Conocimiento wikirag no disponible ({e})")
        return None


class TokenPredictor:
    """P2-6 · predictor lineal (numpy) de tokens de salida a partir de features
    medibles del agente. Aprende del histórico real (sin re-ejecutar). Off hasta
    que exista data/predictor.json."""
    def __init__(self, w=None, b=0.0):
        self.w = w        # lista de pesos
        self.b = b

    @staticmethod
    def features(agent):
        caps = getattr(agent, "caps", [])
        return [
            estimate_tokens(agent.prompt) / 1000.0,         # tamaño del prompt
            len(caps) / 5.0,                                 # nº de capacidades
            len(getattr(agent, "user_query", "")) / 500.0,   # longitud de la petición
            1.0 if any("example" == getattr(c, "role", "") for c in caps) else 0.0,
        ]

    def predict_tokens(self, agent):
        if not self.w:
            return None
        x = self.features(agent)
        y = self.b + sum(wi * xi for wi, xi in zip(self.w, x))
        return max(16.0, y)

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({"w": self.w, "b": self.b}))

    @classmethod
    def load(cls, path):
        p = Path(path)
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text())
            return cls(d.get("w"), d.get("b", 0.0))
        except Exception:
            return None


def build_predictor():
    if os.getenv("MOSAIC_PREDICTOR", "0") != "1":
        return None
    return TokenPredictor.load(os.getenv("MOSAIC_PREDICTOR_PATH", "data/predictor.json"))


# ----------------------------------------------------------------------------
# Motor MOSAIC: el bucle completo
# ----------------------------------------------------------------------------
class MosaicEngine:
    def __init__(self, caps, llm=None, embedder=None, contextualize=True, cache_path=None,
                 light_llm=None):
        self.library = {c.id: c for c in caps}
        self.archived = {}          # capacidades podadas (recuperables, no se borran)
        self.llm = llm or MockLLM()
        self.light = light_llm or self.llm   # 13B para trabajos ligeros (C1)
        self.embedder = embedder or build_embedder()
        self.graph = CompatibilityGraph()
        for c in caps:
            for o in c.compatible_capabilities:
                self.graph.add_compatibility(c.id, o, 0.5)
            for o in c.incompatible_capabilities:
                self.graph.add_incompatibility(c.id, o, "declarado")
        if contextualize:
            Contextualizer(self.light, cache_path).apply(caps)   # ligero
        self.k_final = int(os.getenv("MOSAIC_K_FINAL", "5"))
        self.intent = IntentAnalyzer(self.light)                  # ligero
        self.retriever = HybridRetriever(caps, self.embedder, reranker=build_reranker_bridge())
        self.orch = Orchestrator(self.graph, self.library, self.light)   # transiciones: ligero
        self.evo = Evolution(self.library, self.graph)
        self.knowledge = build_knowledge()      # P1-4: conocimiento wikirag (opcional, off por defecto)
        self.predictor = build_predictor()      # P2-6: predictor de tokens (opcional)
        self.last_metrics = {}                  # P1-3: usage/latencia de la última ejecución

    def compose(self, request):
        intent = self.intent.analyze(request)
        if os.getenv("MOSAIC_CRAG", "1") == "1":
            retrieved, crag = self.retrieve_crag(request, intent)
            if self._fuera_de_dominio(intent, crag):
                # P0-1: nada encaja -> asistente general en crudo (no forzar código)
                self._record_gap(request, intent, crag.get("quality", 0.0))
                agent = self._agente_general(request, intent)
                agent.crag = {**crag, "action": "fallback-general"}
                self._inyectar_conocimiento(agent, request)
                return intent, agent
            if crag.get("gap"):
                self._record_gap(request, intent, crag.get("quality", 0.0))
        else:
            retrieved = self.retriever.retrieve(request, required_domains=intent.domains, k_final=self.k_final)
            crag = {"quality": None, "action": "off", "gap": False}
        agent = self.orch.compose(intent, retrieved, request)
        agent.crag = crag
        self._inyectar_conocimiento(agent, request)
        return intent, agent

    def _agente_general(self, request, intent):
        """Fallback: cuando nada encaja, un asistente general (no fuerza código)."""
        sg = self.library.get("sys-general")
        system = (sg.behavioral_pattern if sg else
                  "Eres un asistente útil, claro y directo. Responde exactamente lo que se "
                  "pregunta, con precisión; no añadas código salvo que te lo pidan.")
        return EphemeralAgent([sg] if sg else [], {}, request, system)

    def _inyectar_conocimiento(self, agent, request):
        if getattr(self, "knowledge", None) is not None:
            try:
                docs = self.knowledge.fetch(request)
                if docs:
                    agent.knowledge = "\n\n".join(docs)
            except Exception as e:
                log(f"conocimiento no disponible ({e})")

    def _fuera_de_dominio(self, intent, crag):
        """True si la petición no encaja: ni sus dominios solapan con la librería, ni
        la mejor capacidad se parece lo suficiente (top_sim bajo)."""
        req = set(intent.domains) - {"general"}
        libd = set()
        for c in self.library.values():
            libd |= set(c.domain_expertise)
        off = bool(req) and not (req & libd)
        sim_min = float(os.getenv("MOSAIC_FALLBACK_SIM", "0.15"))
        top = crag.get("top_sim")
        return off or (isinstance(top, (int, float)) and top < sim_min)

    # --- CRAG: control de calidad de recuperación + detección de huecos ---
    def _semsims(self, request, caps):
        if not caps:
            return []
        q = self.embedder.embed(request)
        M = self.embedder.embed_batch(
            [f"{c.behavioral_pattern} {' '.join(c.domain_expertise)}" for c in caps])
        return [max(0.0, float(M[i] @ q)) for i in range(len(caps))]

    def _crag_quality(self, request, intent, caps):
        """Devuelve (calidad, top_sim): semántica top-3 + cobertura de dominios + score."""
        if not caps:
            return 0.0, 0.0
        sims = sorted(self._semsims(request, caps), reverse=True)
        sem = sum(sims[:3]) / min(3, len(sims))
        top = sims[0]
        req = set(intent.domains) - {"general"}
        if req:
            cub = set()
            for c in caps:
                cub |= (set(c.domain_expertise) & req)
            cov = len(cub) / len(req)
        else:
            cov = 0.5
        perf = sum(c.performance_score for c in caps) / len(caps)
        return max(0.0, min(1.0, 0.5 * sem + 0.3 * cov + 0.2 * perf)), top

    def retrieve_crag(self, request, intent):
        good = float(os.getenv("MOSAIC_CRAG_GOOD", "0.33"))
        poor = float(os.getenv("MOSAIC_CRAG_POOR", "0.18"))
        caps = self.retriever.retrieve(request, required_domains=intent.domains, k_final=self.k_final)
        quality, top = self._crag_quality(request, intent, caps)
        action = "none"
        if quality < good:
            caps2 = self.retriever.retrieve(request, required_domains=None, k_final=self.k_final * 2)
            q2, top2 = self._crag_quality(request, intent, caps2)
            if q2 > quality:
                caps, quality, top, action = caps2[:self.k_final], q2, top2, "expand"
        return caps, {"quality": round(quality, 3), "top_sim": round(top, 3),
                      "action": action, "gap": quality < poor}

    def _record_gap(self, request, intent, quality):
        path = os.getenv("MOSAIC_GAPS", "data/huecos.json")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = []
        if p.exists():
            try:
                data = json.loads(p.read_text())
            except Exception:
                data = []
        data.append({"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "request": request, "domains": intent.domains,
                     "quality": round(quality, 3)})
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        log(f"HUECO de capacidad (calidad {quality:.2f}): {request[:60]}")

    @staticmethod
    def _salida_util(out):
        """¿El mediano entregó algo de verdad? (vacío/error = fallo → reintento/escalada)."""
        t = (out or "").strip()
        return len(t) >= 20 and not t.startswith("[error")

    def execute(self, agent, max_tokens=512, temperature=0.7):
        if getattr(self, "predictor", None) is not None:
            pred = self.predictor.predict_tokens(agent)
            if pred:
                max_tokens = max(64, min(2048, int(pred * 1.3)))   # P2-6: presupuesto dinámico
        # 🪜 Doctrina 3-jul (Gustavo · Opus), endurecida a "EL 24B JAMÁS": el LIGERO rema por
        # defecto; fallo (vacío/error/excepción) → 1 reintento → escala al PRINCIPAL. La escalada
        # es mediano→mediano (Unholy→Qwen3-14B). MOSAIC_ESCALADA=0 = principal directo.
        escalado = False
        if os.getenv("MOSAIC_ESCALADA", "1") != "0" and self.light is not self.llm:
            for _ in (1, 2):
                try:
                    # 🎯 fix madre: máscara=SYSTEM · petición=USER (Opus 16:58 — sitio 1/3)
                    out = self.light.generate(agent.user_text, system=agent.system_text,
                                              max_tokens=max_tokens, temperature=temperature)
                except Exception:
                    out = None
                if self._salida_util(out):
                    self.last_metrics = {"usage": getattr(self.light, "last_usage", {}),
                                         "latency_s": getattr(self.light, "last_latency", 0.0),
                                         "ejecutor": "mediano"}
                    return out
            escalado = True
            log("  🪜 el mediano falló 2 veces → ESCALO esta tarea al modelo PRINCIPAL")
        # 🎯 fix madre (sitio 2/3)
        out = self.llm.generate(agent.user_text, system=agent.system_text,
                                max_tokens=max_tokens, temperature=temperature)
        self.last_metrics = {"usage": getattr(self.llm, "last_usage", {}),
                             "latency_s": getattr(self.llm, "last_latency", 0.0),
                             "ejecutor": "principal-escalado" if escalado else "principal"}
        return out

    def feedback(self, agent, success, quality=1.0):
        self.evo.update(agent, success, quality)
        self.retriever.set_caps(list(self.library.values()))

    # --- poda por redundancia (MMR) + archivo recuperable (Riemann) ---
    def podar_redundantes(self, umbral=0.85):
        """Entre capacidades del MISMO rol con dominios solapados, si la
        similitud coseno >= umbral se archiva la de peor score. Dispara aunque
        la librería sea pequeña y sin necesidad de N muestras: basta con que
        exista un casi-duplicado. No borra: archiva (recuperable)."""
        grupos = defaultdict(list)
        for c in self.library.values():
            grupos[c.role].append(c)

        decisiones = []
        for grupo in grupos.values():
            if len(grupo) < 2:
                continue
            textos = [f"{c.behavioral_pattern} {' '.join(c.domain_expertise)}" for c in grupo]
            M = self.embedder.embed_batch(textos)   # vectores normalizados -> producto = coseno
            for i in range(len(grupo)):
                for j in range(i + 1, len(grupo)):
                    a, b = grupo[i], grupo[j]
                    if not (set(a.domain_expertise) & set(b.domain_expertise)):
                        continue
                    sim = float(M[i] @ M[j])
                    if sim >= umbral:
                        victim, kept = (a, b) if a.performance_score <= b.performance_score else (b, a)
                        decisiones.append((victim.id, kept.id, sim))

        archivadas = []
        for vid, kid, sim in decisiones:
            if vid in self.library and kid in self.library:
                self.archived[vid] = self.library.pop(vid)
                archivadas.append((vid, kid, round(sim, 3)))
                log(f"Poda: '{vid}' archivada (≈ '{kid}', sim {sim:.2f})")

        rescatadas = self._rescatar_dominios_vacios()
        if archivadas or rescatadas:
            self.retriever.set_caps(list(self.library.values()))
        return archivadas, rescatadas

    def _rescatar_dominios_vacios(self):
        """Si un dominio se queda sin NINGUNA capacidad activa tras podar,
        rescata de lo archivado la de mejor score que lo cubra."""
        activos = set()
        for c in self.library.values():
            activos |= set(c.domain_expertise)
        todos = set(activos)
        for c in self.archived.values():
            todos |= set(c.domain_expertise)

        rescatadas = []
        for dom in (todos - activos):
            cands = [c for c in self.archived.values() if dom in c.domain_expertise]
            if cands:
                mejor = max(cands, key=lambda c: c.performance_score)
                if mejor.id in self.archived:
                    self.library[mejor.id] = self.archived.pop(mejor.id)
                    activos |= set(mejor.domain_expertise)
                    rescatadas.append((mejor.id, dom))
                    log(f"Rescate: '{mejor.id}' (el dominio '{dom}' quedaba sin capacidades)")
        return rescatadas

    # --- estado aprendido ---
    def save_state(self, path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        allcaps = {**self.library, **self.archived}
        data = {
            "capabilities": {cid: {"performance_score": c.performance_score,
                                   "usage_count": c.usage_count,
                                   "successful_compositions": c.successful_compositions,
                                   "incompatible_capabilities": c.incompatible_capabilities}
                             for cid, c in allcaps.items()},
            "graph": [{"a": a, "b": b, **attrs} for (a, b), attrs in self.graph.edges.items()],
            "archived": list(self.archived.keys()),
        }
        _escribir_atomico(p, json.dumps(data, indent=2, ensure_ascii=False))

    def load_state(self, path):
        p = Path(path)
        if not p.exists():
            return
        raw = json.loads(p.read_text())
        caps = raw.get("capabilities", raw) if isinstance(raw, dict) else {}
        for cid, s in caps.items():
            c = self.library.get(cid)
            if c:
                c.performance_score = s.get("performance_score", c.performance_score)
                c.usage_count = s.get("usage_count", c.usage_count)
                c.successful_compositions = s.get("successful_compositions", c.successful_compositions)
                c.incompatible_capabilities = s.get("incompatible_capabilities", c.incompatible_capabilities)
        for e in (raw.get("graph", []) if isinstance(raw, dict) else []):
            attrs = {k: v for k, v in e.items() if k not in ("a", "b")}
            if attrs:
                self.graph.edges[(e["a"], e["b"])] = attrs
        # restaurar el conjunto archivado (poda recuperable persistente)
        for aid in (raw.get("archived", []) if isinstance(raw, dict) else []):
            if aid in self.library:
                self.archived[aid] = self.library.pop(aid)
        if hasattr(self, "retriever"):
            self.retriever.set_caps(list(self.library.values()))


# ----------------------------------------------------------------------------
# Librería de capacidades por defecto (POC §5.1) — embebida
# ----------------------------------------------------------------------------
DEFAULT_CAPABILITIES = [
    dict(id="sys-python", role="system_instruction", domain_expertise=["python"],
         performance_score=0.88, tags=["python"],
         behavioral_pattern="Eres un ingeniero Python experto. Escribe Python idiomático, bien tipado y listo para producción; explica brevemente lo no obvio."),
    dict(id="sys-data", role="system_instruction", domain_expertise=["data_analysis", "pandas", "python"],
         performance_score=0.84, tags=["data", "pandas"],
         behavioral_pattern="Eres un analista de datos cuidadoso. Razona sobre formas de datos, distribuciones, valores faltantes y errores estadísticos comunes."),
    dict(id="meth-async-errors", role="methodology", domain_expertise=["async", "error_handling", "python"],
         performance_score=0.86, compatible_capabilities=["ex-async"], incompatible_capabilities=["meth-sync-simple"], tags=["async"],
         behavioral_pattern="Metodología: ejecuta I/O concurrente con asyncio.gather(..., return_exceptions=True); envuelve las llamadas para que los fallos emerjan como contexto de error estructurado y registrado."),
    dict(id="meth-sync-simple", role="methodology", domain_expertise=["python"],
         performance_score=0.62, incompatible_capabilities=["meth-async-errors"], tags=["simple"],
         behavioral_pattern="Metodología: mantén el flujo síncrono y lineal; evita async, hilos y callbacks salvo que la concurrencia sea estrictamente necesaria."),
    dict(id="meth-type-safety", role="methodology", domain_expertise=["type_safety", "python"],
         performance_score=0.83, tags=["types"],
         behavioral_pattern="Metodología: anota todas las firmas, prefiere dataclasses/pydantic para datos estructurados y revisa tipos mentalmente antes de cerrar."),
    dict(id="meth-testing", role="methodology", domain_expertise=["testing", "python"],
         performance_score=0.85, compatible_capabilities=["ex-pytest"], tags=["testing"],
         behavioral_pattern="Metodología: enumera primero los casos límite (camino feliz, fronteras, fallos) y luego escribe pruebas pytest enfocadas a cada uno."),
    dict(id="ex-async", role="example", domain_expertise=["async", "python"], performance_score=0.8, tags=["async"],
         behavioral_pattern="Ejemplo:\n```python\nasync def fetch_all(urls):\n    results = await asyncio.gather(*(fetch(u) for u in urls), return_exceptions=True)\n    return [r for r in results if not isinstance(r, Exception)]\n```"),
    dict(id="ex-pytest", role="example", domain_expertise=["testing", "python"], performance_score=0.8, tags=["testing"],
         behavioral_pattern="Ejemplo:\n```python\ndef test_divide_by_zero():\n    with pytest.raises(ZeroDivisionError):\n        divide(1, 0)\n```"),
    dict(id="con-stdlib-only", role="constraint", domain_expertise=["python"], performance_score=0.78, tags=["constraint"],
         behavioral_pattern="Restricción: usa solo la librería estándar de Python salvo que el usuario pida explícitamente una dependencia externa."),
    dict(id="out-code-block", role="output_specification", domain_expertise=["python"], performance_score=0.82, tags=["output"],
         behavioral_pattern="Salida: devuelve la solución final en un único bloque de código, seguido de como mucho dos frases de explicación."),
    dict(id="meth-pandas", role="methodology", domain_expertise=["pandas", "data_analysis", "python"],
         performance_score=0.6, compatible_capabilities=["ex-pandas"], tags=["pandas", "data"],
         behavioral_pattern="Metodología de datos con pandas: lee ficheros grandes por chunks (read_csv(..., chunksize=...)), normaliza dtypes y trata NaN y filas corruptas de forma explícita. Para análisis usa describe() y quantile() para percentiles, groupby().agg() para agregaciones y corr() para correlaciones; detecta outliers con IQR. Reporta la forma del dataframe y los faltantes."),
    dict(id="ex-pandas", role="example", domain_expertise=["pandas", "data_analysis", "python"],
         performance_score=0.6, tags=["pandas", "data", "example"],
         behavioral_pattern="Ejemplo:\n```python\nimport pandas as pd\ntotal = 0\nfor chunk in pd.read_csv('datos.csv', chunksize=100_000):\n    chunk = chunk.dropna(subset=['valor'])\n    total += chunk['valor'].sum()\np = df['valor'].quantile([0.25, 0.5, 0.9])\ncorr = df.select_dtypes('number').corr()\n```"),
    # --- no-código (la librería deja de ser solo Python) ---
    dict(id="sys-general", role="system_instruction", domain_expertise=["general"], performance_score=0.7, tags=["general"],
         behavioral_pattern="Eres un asistente útil, claro y directo. Responde exactamente lo que se pregunta, con precisión y en lenguaje natural. NO escribas código a menos que la petición lo pida explícitamente."),
    dict(id="meth-explicar", role="methodology", domain_expertise=["general", "explicacion"], performance_score=0.7, tags=["general"],
         behavioral_pattern="Metodología: explica paso a paso, con lenguaje sencillo y ejemplos concretos; define los términos que uses y cierra con una conclusión breve."),
    dict(id="meth-razonar", role="methodology", domain_expertise=["razonamiento", "general"], performance_score=0.7, tags=["general"],
         behavioral_pattern="Metodología: separa hechos de suposiciones, razona en pasos, indica qué das por cierto y qué no se puede afirmar, y evita inventar datos."),
    dict(id="sys-escritura", role="system_instruction", domain_expertise=["escritura", "writing"], performance_score=0.7, tags=["escritura"],
         behavioral_pattern="Eres un escritor claro y conciso. Cuida el tono y la estructura, ve al grano y adapta el registro a quien pregunta."),
    dict(id="out-respuesta-directa", role="output_specification", domain_expertise=["general"], performance_score=0.7, tags=["general"],
         behavioral_pattern="Salida: responde en prosa clara y breve; usa listas solo si ayudan de verdad y no añadas relleno."),
]


def load_capabilities(caps_dir=""):
    if caps_dir:
        d = Path(caps_dir)
        if d.exists():
            try:
                import yaml
                caps = []
                for f in sorted(d.glob("**/*.y*ml")):
                    try:
                        data = yaml.safe_load(f.read_text()) or {}
                    except Exception as e:
                        log(f"saltando {f.name} (yaml ilegible: {e})"); continue
                    # solo ficheros con 'capabilities' (o una lista); los demás (p.ej.
                    # auto_rechazadas.yaml) se ignoran SIN romper la carga.
                    items = data if isinstance(data, list) else data.get("capabilities", [])
                    for it in items:
                        if isinstance(it, dict) and it.get("id"):
                            try:
                                caps.append(Capability(**it))
                            except Exception:
                                pass   # claves desconocidas -> se ignora ese item, no se cae todo
                if caps:
                    return caps
            except ImportError:
                log("pyyaml no instalado; uso capacidades embebidas.")
            except Exception as e:
                log(f"Error leyendo capacidades ({e}); uso embebidas.")
    return [Capability(**d) for d in DEFAULT_CAPABILITIES]


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def endpoint_for(offline, fast):
    if offline:
        return None
    return (os.getenv("MOSAIC_LLM_FAST_URL") if fast else None) or \
        os.getenv("MOSAIC_LLM_BASE_URL", "http://127.0.0.1:8090/v1")


def build_llm(offline, fast):
    base = endpoint_for(offline, fast)
    if base is None:
        return MockLLM(), "mock"
    log(f"LLM -> {base}")
    return ClusterLLM(base, os.getenv("MOSAIC_LLM_MODEL", "local-model")), base


def light_endpoint(offline):
    if offline:
        return None
    return (os.getenv("MOSAIC_LLM_LIGHT_URL") or os.getenv("MOSAIC_LLM_FAST_URL")
            or os.getenv("MOSAIC_LLM_BASE_URL", "http://127.0.0.1:8090/v1"))


def build_light_llm(offline):
    """Cliente 'ligero' (13B en 8091) para trabajos auxiliares: contextualización,
    intención, transiciones y análisis. Así el principal queda libre para ejecutar (C1)."""
    base = light_endpoint(offline)
    if base is None:
        return MockLLM(), "mock"
    return ClusterLLM(base, os.getenv("MOSAIC_LLM_MODEL", "local-model")), base


def judge_endpoint(offline):
    if offline:
        return None
    # MOSAIC_JUDGE_URL: p.ej. el Mac mini (Qwen2.5-3B, el juez pequeño). Si no, el principal.
    return os.getenv("MOSAIC_JUDGE_URL") or os.getenv("MOSAIC_LLM_BASE_URL", "http://127.0.0.1:8090/v1")


def build_judge_llm(offline):
    """Juez: usa MOSAIC_JUDGE_URL si está puesto (descarga el MacBook -> mini);
    si no, el principal. El ejecutor y el generador siguen en el principal."""
    base = judge_endpoint(offline)
    if base is None:
        return MockLLM(), "mock"
    log(f"Juez -> {base}")
    return ClusterLLM(base, os.getenv("MOSAIC_LLM_MODEL", "local-model")), base


def make_engine(offline, fast):
    contextualize = (not offline) and os.getenv("MOSAIC_CONTEXTUALIZE", "1") == "1"
    llm, _ = build_llm(offline, fast)
    light, _ = build_light_llm(offline)
    caps = load_capabilities(os.getenv("MOSAIC_CAPS_DIR", ""))
    cache = os.getenv("MOSAIC_CONTEXT_CACHE", "data/context_cache.json")
    eng = MosaicEngine(caps, llm=llm, light_llm=light, embedder=build_embedder(),
                       contextualize=contextualize, cache_path=cache)
    state = os.getenv("MOSAIC_STATE", "")
    if state:
        eng.load_state(state)
    return eng


JUDGE_PROMPT = """Eres un evaluador EXIGENTE de código generado por un agente. Puntúa con
criterio estricto: la mayoría de respuestas mediocres deben caer en 2-3; reserva el 5
solo para soluciones realmente excelentes y completas.

PETICIÓN:
{request}

CAPACIDADES COMPUESTAS: {caps}

RESPUESTA A EVALUAR:
{output}

Resta puntos si falla cualquiera de esto:
- El código NO está completo o tiene pseudocódigo / "..." / huecos (no sería ejecutable).
- NO cumple todo lo pedido (si pide tests, ¿hay tests reales?; si pide manejo de errores, ¿lo hay?).
- Es incorrecto, no idiomático, o ignora casos límite.
- Se va por las ramas o añade paja en vez de ceñirse a lo pedido.

Escala: 5=excelente y completo · 4=correcto con algún detalle menor · 3=funcional pero
incompleto/flojo · 2=parcial o con fallos · 1=no resuelve. 'resuelto' = true SOLO si nota >= 4.

Devuelve SOLO un JSON con esta forma exacta, sin texto adicional:
{{"uso_capacidades": true, "resuelto": true, "nota": 4, "comentario": "<breve y concreto>"}}"""


def _judge(judge, request, caps, output, prefilter=None):
    """Veredicto JSON sobre una ejecución de MOSAIC. Si hay pre-filtro heurístico
    y detecta FALLA evidente (vacío/error), evita gastar una llamada al juez."""
    if prefilter is not None and output:
        try:
            v, motivo = prefilter.verdict(request, output)
            if v == "FALLA":
                return {"uso_capacidades": True, "resuelto": False, "nota": 1,
                        "comentario": f"prefiltro: {motivo}"}
        except Exception:
            pass
    prompt = JUDGE_PROMPT.format(
        request=request,
        caps=", ".join(caps) or "ninguna",
        output=(output or "(sin respuesta)")[:2000])
    try:
        raw = judge.generate(prompt, max_tokens=220, temperature=0.0)
        return json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
    except Exception as e:
        return {"uso_capacidades": None, "resuelto": None, "nota": None,
                "comentario": f"no parseable: {e}"}


def evaluar(carpeta, offline=False):
    """Autoevaluación: el propio modelo juzga cada resultado de la carpeta."""
    judge, endpoint = build_llm(offline, False)
    folder = Path(carpeta)
    files = sorted(f for f in folder.glob("*.json") if f.name != "evaluacion.json")
    if not files:
        log(f"No hay registros .json en {carpeta}")
        return
    log(f"Evaluando {len(files)} resultados con {endpoint}...")
    veredictos = []
    for f in files:
        try:
            rec = json.loads(f.read_text())
        except Exception as e:
            log(f"  {f.name}: ilegible ({e})")
            continue
        data = _judge(judge, rec.get("request", ""), rec.get("composed", []), rec.get("output"))
        data.update(archivo=f.name, peticion=rec.get("request", ""),
                    capacidades=rec.get("composed", []))
        veredictos.append(data)
        log(f"  {f.name}: nota={data.get('nota')} resuelto={data.get('resuelto')}")

    (folder / "evaluacion.json").write_text(
        json.dumps(veredictos, indent=2, ensure_ascii=False))
    notas = [v["nota"] for v in veredictos if isinstance(v.get("nota"), (int, float))]
    media = sum(notas) / len(notas) if notas else 0.0
    resueltos = sum(1 for v in veredictos if v.get("resuelto") is True)
    lines = ["# Evaluación MOSAIC", "",
             f"- Resultados evaluados: {len(veredictos)}",
             f"- Nota media: {media:.2f}/5",
             f"- Resueltos: {resueltos}/{len(veredictos)}",
             f"- Juez (cluster): {endpoint}", "",
             "| Archivo | Nota | Resuelto | Usó capacidades | Comentario |",
             "|---|---|---|---|---|"]
    for v in veredictos:
        com = str(v.get("comentario", "")).replace("|", "/").replace("\n", " ")[:90]
        lines.append(f"| {v.get('archivo')} | {v.get('nota')} | {v.get('resuelto')} | "
                     f"{v.get('uso_capacidades')} | {com} |")
    (folder / "evaluacion.md").write_text("\n".join(lines))
    print(f"Evaluación -> {folder / 'evaluacion.md'}  "
          f"(media {media:.2f}/5, resueltos {resueltos}/{len(veredictos)})")


ANALISIS_PROMPT = """Eres un analista de sistemas de IA. Te paso el informe de una
tanda de aprendizaje de MOSAIC (sistema que compone agentes a partir de capacidades
que evolucionan con el uso). Analízalo en 6-10 líneas, concreto y accionable:
- ¿Qué capacidades mejoran y cuáles empeoran? ¿Qué sugiere?
- ¿Qué sinergias entre capacidades emergen?
- ¿Qué huecos de capacidad hay y qué capacidad NUEVA crearías para cubrirlos?
- Una recomendación clara para la próxima tanda.

INFORME:
{informe}

HUECOS (peticiones sin capacidad adecuada): {huecos}

Análisis:"""


def analizar(carpeta, offline=False):
    """Cierra el ciclo: el propio modelo (principal) lee el informe de la tanda y emite
    un diagnóstico + recomendación. Guarda analisis.md y lo imprime."""
    judge, endpoint = build_llm(offline, False)   # análisis de calidad -> principal (el ligero salía flojo)
    folder = Path(carpeta)
    informe = folder / "aprendizaje.md"
    if not informe.exists():
        log(f"No hay aprendizaje.md en {carpeta}; nada que analizar")
        return
    texto = informe.read_text()[:4000]
    huecos_txt = "ninguno"
    hp = Path(os.getenv("MOSAIC_GAPS", "data/huecos.json"))
    if hp.exists():
        try:
            hs = json.loads(hp.read_text())
            if hs:
                huecos_txt = "; ".join(h.get("request", "")[:60] for h in hs[-10:])
        except Exception:
            pass
    log(f"Análisis final con el modelo ({endpoint})...")
    try:
        analisis = judge.generate(ANALISIS_PROMPT.format(informe=texto, huecos=huecos_txt),
                                  max_tokens=500, temperature=0.3)
    except Exception as e:
        analisis = f"(No se pudo generar el análisis: {e})"
    (folder / "analisis.md").write_text("# Análisis de la tanda (por el modelo)\n\n" + analisis)
    print("\n===== ANÁLISIS DEL MODELO =====\n")
    print(analisis)
    print(f"\n(guardado en {folder / 'analisis.md'})")


DEFAULT_REQUESTS = [
    "escribe un fetcher async con reintentos y tests",
    "función async que descarga muchas URLs y maneja errores",
    "¿cómo manejo excepciones en asyncio.gather sin que se caiga todo?",
    "escribe tests pytest para una función que divide dos números",
    "tests para una función que parsea fechas en varios formatos",
    "añade anotaciones de tipos a un módulo de usuarios",
    "convierte estas funciones a dataclasses bien tipadas",
    "analiza la distribución de una columna y detecta valores atípicos",
    "lee un csv grande por chunks con pandas y resume por categoría",
    "limpia un dataframe con valores faltantes y filas duplicadas",
    "haz un parser de json sin usar librerías externas",
    "implementa una cola FIFO solo con la librería estándar",
    "escribe una función pura y bien tipada que agrupe una lista por clave",
    "valida un email con expresiones regulares y tests",
    "función async con timeout y reintentos exponenciales",
    "write a python function to retry failed http requests with backoff",
    "write pytest cases for an async URL fetcher",
    "ordena una lista de diccionarios por varias claves",
    "calcula percentiles de una columna numérica en pandas",
    "escribe una clase repositorio en memoria, tipada, con tests",
    "maneja errores de red en una petición y registra el contexto",
    "convierte un script síncrono lento en uno async",
    "detecta y reporta filas corruptas al leer un csv",
    "tests de casos límite para una función factorial",
    "añade type hints y validación a un parser de argumentos",
    "agrupa ventas por mes y calcula la media móvil",
    "función que reintenta una operación hasta 3 veces y propaga el último error",
    "escribe pruebas para código que lanza excepciones personalizadas",
    "normaliza texto (minúsculas, sin acentos) sin dependencias externas",
    "analiza correlaciones entre columnas numéricas",
    "implementa paginación de resultados, tipada y con tests",
    "función async productor/consumidor con manejo de errores",
]


def _bocas_pool(offline, ep_exec):
    """P-F5 (diseño Opus 00:14 · números de Gustavo 01:05): las BOCAS del pool first-to-finish.
    MOSAIC_EXECUTORS = URLs separadas por comas (cruzan las DOS máquinas = 2 GPUs de verdad).
    MOSAIC_WORKERS<=1 → [] (kill-switch: el pipeline/secuencial de siempre, intacto).
    LÍMITE DE GUSTAVO: máx 3 bocas locales en el MacBook — la 4ª concurrente casi lo congela
    (medido 01:08: picos de RAM verticales, Ctrl+C). Se recorta solo.
    Cada boca lleva SU cliente Y SU cliente del principal → CERO estado compartido entre hilos.
    En --offline: mocks (prueban el mecanismo sin red)."""
    try:
        n = int(os.getenv("MOSAIC_WORKERS", "1") or "1")
    except ValueError:
        n = 1
    urls = [u.strip() for u in os.getenv("MOSAIC_EXECUTORS", "").split(",") if u.strip()]
    if n <= 1 or not urls:
        return []
    urls = urls[:max(1, n)]
    locales = [u for u in urls if ("127.0.0.1" in u or "127.0.0.1" in u or "localhost" in u)]
    if len(locales) > 3:
        log("⚠️ >3 bocas locales pedidas → recorto a 3 (límite de Gustavo: la 4ª casi congela el MacBook)")
        fuera = set(locales[3:])
        urls = [u for u in urls if u not in fuera]
    if offline:
        return [(f"mock-{i + 1}", MockLLM(), MockLLM()) for i in range(len(urls))]
    modelo = os.getenv("MOSAIC_LLM_MODEL", "local-model")
    bocas = []
    for u in urls:
        boca = ClusterLLM(u, modelo)
        principal = boca if u == ep_exec else ClusterLLM(ep_exec, modelo)   # mismo objeto si la boca ES el principal
        bocas.append((u.replace("http://", ""), boca, principal))
    return bocas


def _ejecutar_con_boca(engine, agent, nombre, boca, principal, temperature=0.7):
    """Una tarea en UNA boca (doctrina mediano-primero POR BOCA): 2 intentos en la boca;
    sin salida útil → escala a SU cliente del principal (el 8092 lleva --parallel 2 para
    absorber escaladas concurrentes). No escribe estado del engine: cada hilo, su mochila."""
    max_tokens = 512
    pred = getattr(engine, "predictor", None)
    if pred is not None:
        try:
            p = pred.predict_tokens(agent)
            if p:
                max_tokens = max(64, min(2048, int(p * 1.3)))   # P2-6: presupuesto dinámico
        except Exception:
            pass
    escalado = False
    if os.getenv("MOSAIC_ESCALADA", "1") != "0" and boca is not principal:
        for _ in (1, 2):
            try:
                # 🎯 fix madre (sitio 3/3 — las bocas del pool): máscara=SYSTEM · petición=USER
                out = boca.generate(agent.user_text, system=agent.system_text,
                                    max_tokens=max_tokens, temperature=temperature)
            except Exception:
                out = None
            if MosaicEngine._salida_util(out):
                return out, None, {"usage": dict(getattr(boca, "last_usage", {}) or {}),
                                   "latency_s": getattr(boca, "last_latency", 0.0),
                                   "ejecutor": "mediano", "boca": nombre}
        escalado = True
        log(f"  🪜 la boca {nombre} falló 2 veces → ESCALO esta tarea al PRINCIPAL")
    try:
        out, err = principal.generate(agent.user_text, system=agent.system_text,
                                      max_tokens=max_tokens, temperature=temperature), None
    except Exception as e:
        out, err = None, str(e)
    return out, err, {"usage": dict(getattr(principal, "last_usage", {}) or {}),
                      "latency_s": getattr(principal, "last_latency", 0.0),
                      "ejecutor": "principal-escalado" if escalado else "principal", "boca": nombre}


def aprender(ciclos=1, peticiones_file=None, offline=False, fast=False, out=None,
             pipeline=False, ab=None):
    """Bucle de aprendizaje automático a escala.

    Para cada petición: compone -> ejecuta -> el modelo se autojuzga -> el
    veredicto realimenta los scores y el grafo de compatibilidad (en memoria,
    acumulando) -> se persiste el estado. Repite 'ciclos' veces sobre el
    conjunto de peticiones. El estado es acumulativo entre ejecuciones.
    """
    if ab:
        return ab_test(peticiones_file, offline, fast, out, ab)
    if peticiones_file and Path(peticiones_file).exists():
        requests = [ln.strip() for ln in Path(peticiones_file).read_text().splitlines() if ln.strip()]
    else:
        requests = list(DEFAULT_REQUESTS)

    executor, ep_exec = build_llm(offline, fast)       # principal: ejecuta (calidad)
    judge, ep_judge = build_judge_llm(offline)         # juez (mini si MOSAIC_JUDGE_URL; si no principal)
    light, ep_light = build_light_llm(offline)         # 13B: contexto/intención/transiciones/análisis
    if pipeline and not os.getenv("MOSAIC_JUDGE_URL"):
        judge, ep_judge = build_light_llm(offline)     # sin mini: juez al 13B (solapa DENTRO del MacBook)
    # con MOSAIC_JUDGE_URL (mini) el juez ya quedó arriba en el mini -> SOLAPE REAL entre 2 máquinas (#55)
    contextualize = (not offline) and os.getenv("MOSAIC_CONTEXTUALIZE", "1") == "1"
    caps = load_capabilities(os.getenv("MOSAIC_CAPS_DIR", ""))
    engine = MosaicEngine(caps, llm=executor, light_llm=light, embedder=build_embedder(),
                          contextualize=contextualize,
                          cache_path=os.getenv("MOSAIC_CONTEXT_CACHE", "data/context_cache.json"))
    state = os.getenv("MOSAIC_STATE", "data/state.json")
    engine.load_state(state)
    inicial = {cid: c.performance_score for cid, c in engine.library.items()}

    out = out or os.getenv("MOSAIC_RESULTS", "resultados/aprendizaje")
    Path(out).mkdir(parents=True, exist_ok=True)
    total = ciclos * len(requests)
    log(f"Aprendizaje: {ciclos} ciclo(s) x {len(requests)} peticiones = {total} ejecuciones")
    log(f"Ejecutor(principal): {ep_exec} | Juez: {ep_judge} | Ligero: {ep_light}")

    prefilter = build_prefilter()
    if prefilter is not None:
        log(f"Pre-filtro de evaluación activo: {type(prefilter).__name__}")

    records = []
    lock = threading.Lock()

    def procesar(idx, ciclo, req, agent, output, error, metrics):
        """Juzga (fuera del lock) y realimenta + registra (bajo lock)."""
        verdict = _judge(judge, req, [c.id for c in agent.caps], output, prefilter=prefilter)
        nota = verdict.get("nota")
        success = verdict.get("resuelto") is True
        quality = (nota / 5.0) if isinstance(nota, (int, float)) else (1.0 if success else 0.0)
        with lock:
            engine.feedback(agent, success, quality)
            records.append({"n": idx, "ciclo": ciclo, "request": req,
                            "composed": [c.id for c in agent.caps],
                            "output": output,                     # P0: el tribunal (FASE 3) muestrea de aquí (historial = solo USO REAL)
                            "nota": nota, "resuelto": success, "error": error,
                            "crag": agent.crag,
                            "metrics": metrics,                       # P1-3: usage + latencia reales
                            "features": TokenPredictor.features(agent)})  # P2-6: features para el predictor
            if len(records) % 10 == 0:
                engine.save_state(state)
        cq = (agent.crag or {}).get("quality")
        ejec = (metrics or {}).get("ejecutor", "")
        marca = " ⚡" if ejec == "principal-escalado" else ""   # doctrina 3-jul: se VE cuándo entra el gigante
        log(f"[{idx}/{total}] nota={nota} resuelto={success} crag={cq}{marca}"
            f"{' HUECO' if (agent.crag or {}).get('gap') else ''} :: {req[:42]}")

    def compose_execute(req):
        with lock:
            _, agent = engine.compose(req)        # lee/compone -> bajo lock
        output, error = None, None
        try:
            output = engine.execute(agent)        # ejecuta FUERA del lock (puede solapar)
        except Exception as e:
            error = str(e)
        return agent, output, error, dict(engine.last_metrics)   # captura métricas aquí (sin carrera)

    bocas = _bocas_pool(offline, ep_exec)
    if pipeline and bocas:
        # 🐟 P-F5 · POOL first-to-finish (Opus 00:14): M bocas sobre las 2 GPUs; el que acaba,
        # pide más (queue.Queue = claim atómico, sin doble-proceso). Juez con mini-pool propio.
        n_jueces = max(1, int(os.getenv("MOSAIC_JUECES", "2") or "2"))
        log(f"Modo POOL (F5): {len(bocas)} bocas first-to-finish ‖ {n_jueces} hilo(s) de juez en {ep_judge} · kill-switch MOSAIC_WORKERS=1")
        for _nom, _b, _p in bocas:
            log(f"  · boca: {_nom}")
        jq = queue.Queue()

        def judge_worker_pool():
            while True:
                item = jq.get()
                if item is None:
                    jq.task_done()
                    break
                try:
                    procesar(*item)
                except Exception as e:
                    log(f"juez (pool) falló: {e}")
                jq.task_done()

        hilos_juez = []
        for _ in range(n_jueces):
            t = threading.Thread(target=judge_worker_pool, daemon=True)
            t.start()
            hilos_juez.append(t)

        tq = queue.Queue()
        idx = 0
        for ciclo in range(1, ciclos + 1):
            for req in requests:
                idx += 1
                tq.put((idx, ciclo, req))

        def boca_worker(nombre, boca, principal):
            while True:
                try:
                    i, ciclo, req = tq.get_nowait()   # first-to-finish: el que termina, pide más
                except queue.Empty:
                    return
                try:
                    with lock:
                        _, agent = engine.compose(req)          # compone bajo lock (como siempre)
                    output, error, metrics = _ejecutar_con_boca(engine, agent, nombre, boca, principal)
                    jq.put((i, ciclo, req, agent, output, error, metrics))
                except Exception as e:
                    log(f"boca {nombre} falló en [{i}/{total}]: {e}")
                finally:
                    tq.task_done()

        hilos_boca = []
        for _nom, _b, _p in bocas:
            t = threading.Thread(target=boca_worker, args=(_nom, _b, _p), daemon=True)
            t.start()
            hilos_boca.append(t)
        for t in hilos_boca:
            t.join()
        for _ in hilos_juez:
            jq.put(None)
        for t in hilos_juez:
            t.join()
    elif pipeline:
        log(f"Modo PIPELINE: el principal ejecuta la siguiente mientras se juzga la anterior en {ep_judge}.")
        jq = queue.Queue()

        def judge_worker():
            while True:
                item = jq.get()
                if item is None:
                    jq.task_done()
                    break
                try:
                    procesar(*item)
                except Exception as e:
                    log(f"juez (pipeline) falló: {e}")
                jq.task_done()

        worker = threading.Thread(target=judge_worker, daemon=True)
        worker.start()
        idx = 0
        for ciclo in range(1, ciclos + 1):
            for req in requests:
                idx += 1
                agent, output, error, metrics = compose_execute(req)
                jq.put((idx, ciclo, req, agent, output, error, metrics))
        jq.put(None)
        worker.join()
    else:
        idx = 0
        for ciclo in range(1, ciclos + 1):
            for req in requests:
                idx += 1
                agent, output, error, metrics = compose_execute(req)
                procesar(idx, ciclo, req, agent, output, error, metrics)

    records.sort(key=lambda r: r["n"])
    notas = [r["nota"] for r in records if isinstance(r["nota"], (int, float))]
    resueltos = sum(1 for r in records if r["resuelto"])
    crag_qs = [(r.get("crag") or {}).get("quality") for r in records
               if isinstance((r.get("crag") or {}).get("quality"), (int, float))]
    huecos = sum(1 for r in records if (r.get("crag") or {}).get("gap"))
    n = len(records)

    # poda por redundancia (+ rescate de dominios vacíos) al cerrar la tanda
    umbral = float(os.getenv("MOSAIC_PODA_UMBRAL", "0.85"))
    archivadas, rescatadas = engine.podar_redundantes(umbral=umbral)
    engine.save_state(state)

    Path(out, "registros.json").write_text(json.dumps(records, indent=2, ensure_ascii=False))
    media = sum(notas) / len(notas) if notas else 0.0

    filas = []
    for cid, c in engine.library.items():
        ini = inicial.get(cid, c.performance_score)
        filas.append((cid, c.role, ini, c.performance_score, c.performance_score - ini, c.usage_count))
    filas.sort(key=lambda x: x[4], reverse=True)

    syn = defaultdict(int)
    for c in engine.library.values():
        for other, k in c.successful_compositions.items():
            syn[tuple(sorted((c.id, other)))] = max(syn[tuple(sorted((c.id, other)))], k)
    top_syn = sorted(syn.items(), key=lambda x: x[1], reverse=True)[:10]

    lines = ["# Aprendizaje MOSAIC", "",
             f"- Ejecuciones: {n}  ({ciclos} ciclo(s) x {len(requests)} peticiones)",
             f"- Nota media: {media:.2f}/5   ·   Resueltos: {resueltos}/{n}",
             f"- Ejecutor: {ep_exec}   ·   Juez: {ep_judge}",
             f"- Estado acumulado en: {state}", "",
             "## Evolución de capacidades (orden por Δ)", "",
             "| Capacidad | Rol | Inicial | Final | Δ | Usos |",
             "|---|---|---|---|---|---|"]
    for cid, role, ini, fin, d, u in filas:
        lines.append(f"| {cid} | {role} | {ini:.3f} | {fin:.3f} | {d:+.3f} | {u} |")
    lines += ["", "## Sinergias aprendidas (co-activaciones exitosas)", ""]
    if top_syn:
        lines += ["| Par | Veces |", "|---|---|"]
        for (a, b), k in top_syn:
            lines.append(f"| {a} + {b} | {k} |")
    else:
        lines.append("(aún ninguna)")

    lines += ["", f"## Poda por redundancia (umbral coseno {umbral})", ""]
    if archivadas:
        lines += ["| Archivada | ≈ Conservada | Similitud |", "|---|---|---|"]
        for vid, kid, sim in archivadas:
            lines.append(f"| {vid} | {kid} | {sim} |")
    else:
        lines.append("(sin redundancias por encima del umbral)")
    if rescatadas:
        lines += ["", "Rescatadas para no dejar dominios sin capacidades:"]
        for rid, dom in rescatadas:
            lines.append(f"- {rid} (dominio '{dom}')")
    if engine.archived:
        lines += ["", f"Archivadas activas (recuperables): {', '.join(engine.archived)}"]

    crag_media = sum(crag_qs) / len(crag_qs) if crag_qs else 0.0
    lines += ["", "## CRAG: calidad de recuperación y huecos", "",
              f"- Calidad media de recuperación: {crag_media:.3f}",
              f"- Huecos detectados (sin capacidad adecuada): {huecos}/{n}"]
    if huecos:
        lines.append(f"- Semillas para nuevas capacidades en: {os.getenv('MOSAIC_GAPS', 'data/huecos.json')}")

    Path(out, "aprendizaje.md").write_text("\n".join(lines))
    print(f"Aprendizaje -> {Path(out, 'aprendizaje.md')}  "
          f"(media {media:.2f}/5, resueltos {resueltos}/{n}, "
          f"calidad CRAG {crag_media:.2f}, huecos {huecos})")

    # ciclo completo: el modelo analiza la tanda y deja recomendaciones
    analizar(out, offline=offline)

    # A/B integrado (C3): tras aprender, mide composición vs 'raw' (u otro modelo)
    # sobre una muestra, sin que tengas que lanzar nada aparte.
    ab_target = os.getenv("MOSAIC_AB", "raw").strip()
    m = os.getenv("MOSAIC_AB_MUESTRA", "6").strip().lower()
    if ab_target and ab_target.lower() not in ("0", "no", "off") and m not in ("0", "no", "off"):
        muestra = requests if m == "all" else requests[:max(1, int(m) if m.isdigit() else 6)]
        ab_judge, ep_abj = build_judge_llm(offline)   # juez del A/B (mini si MOSAIC_JUDGE_URL)
        log(f"A/B integrado: {len(muestra)} peticiones (A=composición vs B={ab_target})")
        _run_ab(engine, ab_judge, prefilter, muestra, ab_target, out, ep_exec, ep_abj)


def _safe_exec(llm, prompt, max_tokens=512):
    try:
        return llm.generate(prompt, max_tokens=max_tokens, temperature=0.7)
    except Exception as e:
        return f"(error de ejecución: {e})"


def _run_ab(engine, judge, prefilter, requests, ab_target, out, ep_a="", ep_j=""):
    """Núcleo A/B: arm A = composición (engine.llm) · arm B = 'raw' (mismo modelo
    sin composición) o '<url>' (otro modelo). Escribe comparativa.md."""
    if ab_target == "raw":
        exec_b, label_b = engine.llm, "prompt CRUDO (sin MOSAIC)"
    else:
        exec_b, label_b = ClusterLLM(ab_target, os.getenv("MOSAIC_LLM_MODEL", "local-model")), f"composición en {ab_target}"
    Path(out).mkdir(parents=True, exist_ok=True)
    rows, sumA, sumB, winA, winB, ties = [], 0, 0, 0, 0, 0
    for i, req in enumerate(requests, 1):
        intent, agent = engine.compose(req)
        ids = [c.id for c in agent.caps]
        dom = (intent.domains[0] if getattr(intent, "domains", None) else "general")
        outA = _safe_exec(engine.llm, agent.prompt)
        outB = _safe_exec(exec_b, req if ab_target == "raw" else agent.prompt)
        nA = _judge(judge, req, ids, outA, prefilter=prefilter).get("nota")
        nB = _judge(judge, req, ids, outB, prefilter=prefilter).get("nota")
        nA = nA if isinstance(nA, (int, float)) else 0
        nB = nB if isinstance(nB, (int, float)) else 0
        sumA += nA
        sumB += nB
        w = "A" if nA > nB else "B" if nB > nA else "="
        winA += w == "A"
        winB += w == "B"
        ties += w == "="
        rows.append({"request": req, "dominio": dom, "notaA": nA, "notaB": nB, "ganador": w})
        log(f"  [A/B {i}/{len(requests)}] A={nA} B={nB} -> {w} :: {req[:40]}")
    n = len(requests) or 1
    Path(out, "ab.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    veredicto = ("la composición de MOSAIC AYUDA" if sumA > sumB
                 else "la composición NO mejora aquí" if sumA < sumB else "empate técnico")
    # P3-8: desglose por dominio
    por_dom = {}
    for r in rows:
        d = por_dom.setdefault(r["dominio"], [0.0, 0.0, 0])
        d[0] += r["notaA"]
        d[1] += r["notaB"]
        d[2] += 1
    lines = ["# Comparativa A/B", "",
             f"- A = composición MOSAIC @ {ep_a}",
             f"- B = {label_b}",
             f"- Juez @ {ep_j} · {len(requests)} peticiones", "",
             f"- Nota media A: {sumA / n:.2f}/5   ·   Nota media B: {sumB / n:.2f}/5",
             f"- Gana A: {winA} · Gana B: {winB} · Empates: {ties}",
             f"- Veredicto: {veredicto}", "",
             "## Por dominio (¿dónde ayuda la composición?)", "",
             "| Dominio | A | B | n |", "|---|---|---|---|"]
    for d, (sa, sb, c) in sorted(por_dom.items(), key=lambda x: -x[1][2]):
        lines.append(f"| {d} | {sa / c:.2f} | {sb / c:.2f} | {c} |")
    lines += ["", "## Detalle", "", "| Petición | Dom | A | B | Ganador |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['request'][:44]} | {r['dominio']} | {r['notaA']} | {r['notaB']} | {r['ganador']} |")
    Path(out, "comparativa.md").write_text("\n".join(lines))
    print(f"A/B -> {Path(out, 'comparativa.md')}  (A {sumA / n:.2f} vs B {sumB / n:.2f}/5 · {veredicto})")
    return sumA / n, sumB / n


def ab_test(peticiones_file=None, offline=False, fast=False, out=None, ab_target="raw"):
    """C3 · A/B. Arm A = composición de MOSAIC en el principal. Arm B = 'raw' (mismo modelo
    SIN composición, para medir cuánto aporta MOSAIC) o '<url>' (la composición en otro
    modelo, para comparar modelos). El juez puntúa ambos. No persiste aprendizaje."""
    if peticiones_file and Path(peticiones_file).exists():
        requests = [ln.strip() for ln in Path(peticiones_file).read_text().splitlines() if ln.strip()]
    else:
        requests = list(DEFAULT_REQUESTS)

    executor, ep_a = build_llm(offline, fast)
    light, _ = build_light_llm(offline)
    judge, ep_j = build_llm(offline, False)
    caps = load_capabilities(os.getenv("MOSAIC_CAPS_DIR", ""))
    engine = MosaicEngine(caps, llm=executor, light_llm=light, embedder=build_embedder(),
                          contextualize=(not offline) and os.getenv("MOSAIC_CONTEXTUALIZE", "1") == "1",
                          cache_path=os.getenv("MOSAIC_CONTEXT_CACHE", "data/context_cache.json"))
    engine.load_state(os.getenv("MOSAIC_STATE", "data/state.json"))
    out = out or os.getenv("MOSAIC_RESULTS", "resultados/ab")
    _run_ab(engine, judge, build_prefilter(), requests, ab_target, out, ep_a, ep_j)


def _log_historial(request, agent, output, error, metrics=None):
    """Registra cada uso real de mosaic.sh en una cola JSONL para 'consolidar'."""
    if os.getenv("MOSAIC_LOG", "1") != "1" or not request:
        return
    path = Path(os.getenv("MOSAIC_HISTORIAL", "data/historial.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "request": request,
           "fuente": os.getenv("MOSAIC_FUENTE", ""),   # qué modelo generó la petición (matices)
           "composed": [c.id for c in agent.caps], "output": output, "error": error,
           "metrics": metrics or {}, "features": TokenPredictor.features(agent)}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def consolidar(offline=False, out=None):
    """Opción 1 · aprende del USO REAL. Lee la cola que registró mosaic.sh
    (data/historial.jsonl), JUZGA cada respuesta YA generada (sin re-ejecutar),
    realimenta scores+grafo y persiste; luego archiva la cola y la vacía."""
    hist = Path(os.getenv("MOSAIC_HISTORIAL", "data/historial.jsonl"))
    _recuperar_huerfanos(hist, "historial.consolidando_*.jsonl")   # retoma cortes previos (Ctrl+C)
    # ATÓMICO: reclama la cola por renombrado; los usos que entren mientras consolida
    # van a un historial.jsonl nuevo y NO se pierden.
    work = hist
    if hist.exists() and hist.stat().st_size > 0:
        cand = hist.with_name(hist.stem + f".consolidando_{time.strftime('%Y%m%d_%H%M%S')}" + hist.suffix)
        try:
            hist.rename(cand)
            work = cand
        except Exception:
            work = hist

    def _hay_contenido(p):                          # ¿algo que consolidar? sin cargar todo en memoria
        if not p.exists():
            return False
        with open(p, encoding="utf-8") as fh:
            return any(ln.strip() for ln in fh)
    if not _hay_contenido(work):
        log('Historial vacío: usa ./mosaic.sh "tu tarea" antes de consolidar.')
        return

    judge, ep_j = build_judge_llm(offline)        # juez al mini si MOSAIC_JUDGE_URL está puesto
    light, _ = build_light_llm(offline)
    caps = load_capabilities(os.getenv("MOSAIC_CAPS_DIR", ""))
    engine = MosaicEngine(caps, llm=judge, light_llm=light, embedder=build_embedder(),
                          contextualize=False,
                          cache_path=os.getenv("MOSAIC_CONTEXT_CACHE", "data/context_cache.json"))
    state = os.getenv("MOSAIC_STATE", "data/state.json")
    engine.load_state(state)
    inicial = {cid: c.performance_score for cid, c in engine.library.items()}
    prefilter = build_prefilter()
    out = out or os.getenv("MOSAIC_RESULTS", "resultados/consolidado")
    Path(out).mkdir(parents=True, exist_ok=True)
    # A/B: config leída ya, para juntar las peticiones únicas DURANTE el streaming (sin re-leer ni lista entera)
    ab_target = os.getenv("MOSAIC_AB", "raw").strip()
    ab_m = os.getenv("MOSAIC_AB_MUESTRA", "5").strip().lower()
    ab_on = bool(ab_target) and ab_target.lower() not in ("0", "off", "no")
    ab_lim = (10 ** 9 if ab_m == "all" else (int(ab_m) if ab_m.isdigit() else 5))
    reqs, _vistos_ab = [], set()
    total = sum(1 for ln in open(work, encoding="utf-8") if ln.strip())   # conteo barato (no retiene)
    log(f"Consolidando {total} usos reales (juez {ep_j}, sin re-ejecutar, en streaming)...")

    notas, aplicados, i = [], 0, 0
    por_fuente = defaultdict(list)
    with open(work, encoding="utf-8") as fh:          # STREAMING: una línea a la vez (memoria O(1))
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except Exception:
                continue
            i += 1
            if ab_on and len(reqs) < ab_lim:            # junta peticiones únicas para el A/B (en streaming)
                _r = (rec.get("request") or "").strip()
                if _r and _r.lower() not in _vistos_ab:
                    _vistos_ab.add(_r.lower()); reqs.append(_r)
            ids = [c for c in rec.get("composed", []) if c in engine.library]
            if not ids:
                continue
            agent = EphemeralAgent([engine.library[c] for c in ids], {}, rec.get("request", ""), "")
            verdict = _judge(judge, rec.get("request", ""), ids, rec.get("output"), prefilter=prefilter)
            nota = verdict.get("nota")
            success = verdict.get("resuelto") is True
            quality = (nota / 5.0) if isinstance(nota, (int, float)) else (1.0 if success else 0.0)
            engine.feedback(agent, success, quality)
            if isinstance(nota, (int, float)):
                notas.append(nota)
                por_fuente[rec.get("fuente") or "?"].append(nota)
            aplicados += 1
            log(f"  [{i}/{total}] nota={nota} :: {rec.get('request', '')[:50]}")

    engine.podar_redundantes(umbral=float(os.getenv("MOSAIC_PODA_UMBRAL", "0.85")))
    engine.save_state(state)

    # archivar la cola consolidada (permanente, en streaming) y retirar el archivo de trabajo
    archivo = hist.with_name(hist.stem + ".consolidado" + hist.suffix)
    with open(archivo, "a", encoding="utf-8") as f, open(work, encoding="utf-8") as fh:
        for raw in fh:
            if raw.strip():
                f.write(raw if raw.endswith("\n") else raw + "\n")
    if work != hist and work.exists():          # atómico OK: ya archivado -> a la papelera
        try:
            trash = hist.parent.parent / "trash" / "historico"
            trash.mkdir(parents=True, exist_ok=True)
            work.rename(trash / work.name)
        except Exception:
            pass
    else:
        hist.write_text("")                     # no se pudo renombrar: vaciar (clásico)

    media = sum(notas) / len(notas) if notas else 0.0
    filas = sorted(((cid, c.performance_score - inicial.get(cid, c.performance_score), c.performance_score)
                    for cid, c in engine.library.items()), key=lambda x: x[1], reverse=True)
    lines = ["# Consolidación · aprendizaje del uso real", "",
             f"- Usos consolidados: {aplicados}  ·  nota media: {media:.2f}/5",
             f"- Juez: {ep_j}  ·  estado: {state}",
             f"- Cola archivada en: {archivo.name} (la cola queda vacía)", "",
             "| Capacidad | Δ | Final |", "|---|---|---|"]
    for cid, d, fin in filas:
        lines.append(f"| {cid} | {d:+.3f} | {fin:.3f} |")
    fuentes_reales = {k: v for k, v in por_fuente.items() if k != "?"}
    if fuentes_reales:
        lines += ["", "## Por fuente — qué modelo generó la pregunta", "",
                  "| Fuente | Usos | Nota media |", "|---|---|---|"]
        for fuente, ns in sorted(fuentes_reales.items(),
                                 key=lambda x: -(sum(x[1]) / len(x[1])) if x[1] else 0):
            lines.append(f"| {fuente} | {len(ns)} | {sum(ns) / len(ns):.2f} |")
    Path(out, "consolidacion.md").write_text("\n".join(lines))
    print(f"Consolidado -> {Path(out, 'consolidacion.md')}  ({aplicados} usos reales, nota media {media:.2f}/5)")

    # A/B automático: ¿la composición ACTUAL gana al prompt crudo, sobre tus usos reales?
    if ab_on:                                           # config ya leída arriba; reqs recogidas en streaming
        if reqs:
            ab_judge, ep_ab = build_judge_llm(offline)
            log(f"A/B automático: {len(reqs)} usos reales (composición vs {ab_target})")
            _run_ab(engine, ab_judge, prefilter, reqs, ab_target, out, ep_j, ep_ab)


GEN_PROMPT = """Eres un diseñador de capacidades para un sistema de composición de agentes.
Dada una petición que el sistema NO supo resolver bien, redacta UNA capacidad GENERAL y
reutilizable que ayude con MUCHAS peticiones de ese tipo (no la respuesta a ESTA).

REGLA CLAVE: NO escribas la receta de ESTA petición. NO empieces con "Para [la petición]...".
Escribe una instrucción imperativa y general, aplicable a casos parecidos.
  MAL:  "Para leer un CSV grande, primero define el tamaño del chunk y luego itera..."
  BIEN: "Cuando proceses ficheros grandes, léelos por trozos (streaming) y valida cada trozo
         antes de continuar; nunca cargues todo en memoria."

PETICIÓN: {request}
DOMINIOS: {domains}

Devuelve SOLO un JSON:
{{"id": "<slug-corto>", "role": "system_instruction|methodology|example|constraint|output_specification",
"domain_expertise": ["dominio1","dominio2"], "behavioral_pattern": "<instrucción GENERAL, imperativa, NO la respuesta>"}}"""


CURATE_PROMPT = """Eres un revisor ESTRICTO de "capacidades" reutilizables para un sistema de composición de agentes.
Una buena capacidad es una INSTRUCCIÓN general y reutilizable (NO la respuesta a un caso concreto), clara y no trivial.
Evalúa esta:
  id: {id}   role: {role}   dominios: {domains}
  instrucción: {pattern}
Puntúa de 0 a 10 (10 = excelente y reutilizable; 0 = inútil, trivial o es una respuesta concreta).
Devuelve SOLO JSON: {{"nota": <entero 0-10>, "motivo": "<una frase>"}}"""


def _nt(prompt):
    """P-L3 (3-jul, probado a mano): Qwen3 RAZONA por defecto y el pensamiento se come los
    max_tokens cortos → content vacío → json.loads falla ("Expecting value: line 1 column 1").
    /no_think (interruptor suave oficial de Qwen3) SOLO si el motor declarado es Qwen3;
    a otros motores no se les toca el prompt."""
    return ("/no_think " + prompt) if "qwen3" in os.getenv("MOSAIC_LLM_MODEL", "").lower() else prompt


def _curar_capacidad(llm, cap):
    """El modelo valida/puntúa una capacidad. Devuelve (nota 0-10, motivo) o (None, '').
    Ojo (P-L3): si el LLM se ahoga aquí devuelve (None,'') y la capacidad pasa SIN curar —
    por eso el /no_think + oxígeno importan también en esta llamada."""
    try:
        raw = llm.generate(_nt(CURATE_PROMPT.format(id=cap.id, role=cap.role,
                           domains=cap.domain_expertise, pattern=cap.behavioral_pattern)),
                           max_tokens=300, temperature=0.0)
        d = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        return float(d.get("nota")), str(d.get("motivo", ""))[:140]
    except Exception:
        return None, ""


def generar_capacidades(offline=False, out=None):
    """P2-5 · cierra el círculo: por cada hueco, el modelo redacta una capacidad nueva
    y la añade a capabilities/auto_generadas.yaml; archiva los huecos procesados."""
    gp = Path(os.getenv("MOSAIC_GAPS", "data/huecos.json"))
    _recuperar_huerfanos(gp, "huecos.procesando_*.json")   # retoma cortes previos (Ctrl+C)
    try:
        pre = json.loads(gp.read_text() or "[]") if gp.exists() else []
    except Exception:
        pre = []
    if not pre:
        log("No hay huecos que cubrir todavía.")
        return
    # ATÓMICO: renombra la cola antes de leerla; los huecos NUEVOS van a un huecos.json limpio
    work = gp.with_name(gp.stem + f".procesando_{time.strftime('%Y%m%d_%H%M%S')}" + gp.suffix)
    try:
        gp.rename(work)
    except Exception:
        work = gp
    try:
        gaps = json.loads(work.read_text() or "[]")
    except Exception:
        gaps = []
    llm, ep = build_llm(offline, False)
    curar = os.getenv("MOSAIC_CURAR", "1") == "1"
    umbral_cur = float(os.getenv("MOSAIC_CURAR_UMBRAL", "6"))
    existing = {c.id for c in load_capabilities(os.getenv("MOSAIC_CAPS_DIR", ""))}
    vistos, unicos = set(), []
    for g in gaps:
        r = (g.get("request") or "").strip()
        if r and r.lower() not in vistos:
            vistos.add(r.lower())
            unicos.append(g)
    nuevas, rechazadas = [], []
    for g in unicos[:int(os.getenv("MOSAIC_GEN_MAX", "8"))]:
        try:
            raw = llm.generate(_nt(GEN_PROMPT.format(request=g["request"], domains=g.get("domains", []))),
                               max_tokens=500, temperature=0.3)
            data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
            cap = Capability(id=str(data["id"]), role=str(data["role"]),
                             domain_expertise=data.get("domain_expertise") or ["general"],
                             behavioral_pattern=str(data["behavioral_pattern"]),
                             performance_score=0.55, tags=["auto"])
            if cap.id in existing:
                cap.id += "-auto"
            if curar:   # CURACIÓN: el modelo valida/puntúa la capacidad ANTES de añadirla
                nota_c, motivo = _curar_capacidad(llm, cap)
                if isinstance(nota_c, (int, float)) and nota_c < umbral_cur:
                    rechazadas.append({"id": cap.id, "nota": nota_c, "motivo": motivo,
                                       "role": cap.role, "domain_expertise": cap.domain_expertise,
                                       "behavioral_pattern": cap.behavioral_pattern})
                    log(f"  ✗ descartada {cap.id} (curación {nota_c:.0f}/10 < {umbral_cur:.0f}): {motivo}")
                    continue
                if isinstance(nota_c, (int, float)):
                    cap.performance_score = max(0.4, min(0.7, nota_c / 10.0))
            existing.add(cap.id)
            nuevas.append(cap)
            log(f"  + {cap.id} ({cap.role}) {cap.domain_expertise}")
        except Exception as e:
            log(f"  fallo generando para '{g.get('request', '')[:40]}': {e}")
    if nuevas:
        try:
            import yaml
            dest = Path(os.getenv("MOSAIC_CAPS_DIR", "capabilities")) / "auto_generadas.yaml"
            items = (yaml.safe_load(dest.read_text()) or {}).get("capabilities", []) if dest.exists() else []
            for c in nuevas:
                items.append({"id": c.id, "role": c.role, "domain_expertise": c.domain_expertise,
                              "behavioral_pattern": c.behavioral_pattern,
                              "performance_score": c.performance_score, "tags": c.tags})
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(yaml.safe_dump({"capabilities": items}, allow_unicode=True, sort_keys=False))
        except Exception as e:
            log(f"No se pudo escribir auto_generadas.yaml ({e})")
    if rechazadas:   # registro de descartadas (transparencia para revisar)
        try:
            import yaml
            rp = Path(os.getenv("MOSAIC_STATE", "data/state.json")).parent / "auto_rechazadas.yaml"
            prev_r = (yaml.safe_load(rp.read_text()) or {}).get("rechazadas", []) if rp.exists() else []
            rp.write_text(yaml.safe_dump({"rechazadas": prev_r + rechazadas}, allow_unicode=True, sort_keys=False))
        except Exception as e:
            log(f"No se pudo escribir auto_rechazadas.yaml ({e})")
    arch = gp.with_name("huecos.consolidado.json")   # archivo permanente de huecos procesados
    prev = json.loads(arch.read_text() or "[]") if arch.exists() else []
    arch.write_text(json.dumps(prev + gaps, ensure_ascii=False, indent=2))
    if work != gp:                                   # atómico OK: retira el archivo de trabajo a la papelera
        try:
            trash = gp.parent.parent / "trash" / "historico"
            trash.mkdir(parents=True, exist_ok=True)
            work.rename(trash / work.name)
        except Exception:
            pass
    else:
        gp.write_text("[]")                          # no se pudo renombrar: vaciamos la cola (clásico)
    print(f"Generadas {len(nuevas)} capacidades nuevas, {len(rechazadas)} descartadas, desde {len(unicos)} huecos.")


def curar_existentes(offline=False, out=None):
    """Pasa el juez por las capacidades auto-generadas YA existentes: puntúa cada una y
    mueve las flojas (< MOSAIC_CURAR_UMBRAL) a data/auto_rechazadas.yaml. Backup antes."""
    import yaml
    dest = Path(os.getenv("MOSAIC_CAPS_DIR", "capabilities")) / "auto_generadas.yaml"
    if not dest.exists():
        log("No hay auto_generadas.yaml que curar."); return
    items = (yaml.safe_load(dest.read_text()) or {}).get("capabilities", [])
    if not items:
        log("auto_generadas.yaml vacío."); return
    llm, ep = build_judge_llm(offline)
    umbral = float(os.getenv("MOSAIC_CURAR_UMBRAL", "6"))
    bak = dest.with_name(dest.stem + f".pre_curado_{time.strftime('%Y%m%d_%H%M%S')}" + dest.suffix)
    bak.write_text(dest.read_text())                     # backup recuperable
    log(f"Curando {len(items)} capacidades (juez {ep}, umbral {umbral:.0f})...")
    buenas, malas = [], []
    for it in items:
        if not (isinstance(it, dict) and it.get("id")):
            continue
        try:
            cap = Capability(**it)
        except Exception:
            buenas.append(it); continue                  # no evaluable -> la dejo
        nota, motivo = _curar_capacidad(llm, cap)
        if isinstance(nota, (int, float)) and nota < umbral:
            it2 = dict(it); it2["nota"], it2["motivo"] = nota, motivo
            malas.append(it2)
            log(f"  ✗ {cap.id}: {nota:.0f}/10 :: {motivo}")
        else:
            if isinstance(nota, (int, float)):
                it["performance_score"] = max(0.4, min(0.7, nota / 10.0))
            buenas.append(it)
    dest.write_text(yaml.safe_dump({"capabilities": buenas}, allow_unicode=True, sort_keys=False))
    if malas:
        rp = Path(os.getenv("MOSAIC_STATE", "data/state.json")).parent / "auto_rechazadas.yaml"
        rp.parent.mkdir(parents=True, exist_ok=True)
        prev = (yaml.safe_load(rp.read_text()) or {}).get("rechazadas", []) if rp.exists() else []
        rp.write_text(yaml.safe_dump({"rechazadas": prev + malas}, allow_unicode=True, sort_keys=False))
    print(f"Curación: se quedan {len(buenas)}, descartadas {len(malas)} (backup: {bak.name}).")


def _leer_registros():
    import glob
    base = os.getenv("MOSAIC_RESULTS_DIR", "resultados")
    recs = []
    for f in glob.glob(os.path.join(base, "**", "registros.json"), recursive=True):
        try:
            recs += json.loads(Path(f).read_text())
        except Exception:
            pass
    return recs


def entrenar_predictor(out=None):
    """P2-6 · entrena el predictor de tokens (features -> completion_tokens reales)."""
    X, y = [], []
    for r in _leer_registros():
        feats = r.get("features")
        ct = (r.get("metrics") or {}).get("usage", {}).get("completion_tokens")
        if feats and isinstance(ct, (int, float)):
            X.append(feats)
            y.append(float(ct))
    if len(X) < 8:
        log(f"Pocos datos para el predictor ({len(X)}); usa más y reentrena.")
        return
    A = np.array([xi + [1.0] for xi in X])
    sol, *_ = np.linalg.lstsq(A, np.array(y), rcond=None)
    path = os.getenv("MOSAIC_PREDICTOR_PATH", "data/predictor.json")
    TokenPredictor(list(sol[:-1]), float(sol[-1])).save(path)
    print(f"Predictor entrenado con {len(X)} muestras -> {path}")


def entrenar_reward(out=None):
    """P3-7 · reward model lineal e interpretable: aprende el peso de cada capacidad
    hacia notas altas, a partir de los registros. Guarda data/reward.json + informe."""
    vocab = sorted({c.id for c in load_capabilities(os.getenv("MOSAIC_CAPS_DIR", ""))})
    idx = {c: i for i, c in enumerate(vocab)}
    X, y = [], []
    for r in _leer_registros():
        nota = r.get("nota")
        if not isinstance(nota, (int, float)):
            continue
        vec = [0.0] * len(vocab)
        for cid in r.get("composed", []):
            if cid in idx:
                vec[idx[cid]] = 1.0
        X.append(vec)
        y.append(float(nota) / 5.0)
    if len(X) < 10:
        log(f"Pocos datos para el reward model ({len(X)}).")
        return
    A = np.array([xi + [1.0] for xi in X])
    sol, *_ = np.linalg.lstsq(A, np.array(y), rcond=None)
    w = list(sol[:-1])
    path = os.getenv("MOSAIC_REWARD_PATH", "data/reward.json")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"vocab": vocab, "w": w, "b": float(sol[-1])}, ensure_ascii=False))
    pares = sorted(zip(vocab, w), key=lambda t: t[1], reverse=True)
    lines = ["# Reward model · contribución aprendida por capacidad", "",
             f"- muestras: {len(X)}", "", "| Capacidad | Peso |", "|---|---|"]
    lines += [f"| {cid} | {wi:+.3f} |" for cid, wi in pares]
    rep = Path(out, "reward.md") if out else Path("data/reward.md")
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text("\n".join(lines))
    print(f"Reward model entrenado con {len(X)} muestras -> {path}  (informe: {rep})")


def servidor(port=8077, offline=False):
    """P4-9 · MOSAIC como API OpenAI-compatible. Apunta cualquier cliente aquí y
    recibirá la respuesta YA compuesta por MOSAIC."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    eng = make_engine(offline, False)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
                req = body.get("prompt", "")
                for m in reversed(body.get("messages", [])):
                    if m.get("role") == "user":
                        req = m.get("content", "")
                        break
                intent, agent = eng.compose(req)
                outp = eng.execute(agent, max_tokens=int(body.get("max_tokens", 512)),
                                   temperature=float(body.get("temperature", 0.7)))
                _log_historial(req, agent, outp, None, getattr(eng, "last_metrics", {}))
                resp = {"id": "mosaic", "object": "chat.completion",
                        "choices": [{"index": 0, "finish_reason": "stop",
                                     "message": {"role": "assistant", "content": outp}}],
                        "mosaic": {"composed": [c.id for c in agent.caps], "crag": agent.crag}}
                data = json.dumps(resp, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                data = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

    log(f"MOSAIC servidor OpenAI-compatible en http://0.0.0.0:{port}/v1/chat/completions (Ctrl+C para parar)")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


def selftest():
    log("selftest: construyendo motor offline...")
    eng = MosaicEngine([Capability(**d) for d in DEFAULT_CAPABILITIES],
                       llm=MockLLM(), embedder=HashingEmbedder(256), contextualize=False)
    intent, agent = eng.compose("escribe una función async en python con manejo de errores y tests")
    ids = [c.id for c in agent.caps]
    assert agent.caps, "no se compuso ningún agente"
    assert not ("meth-async-errors" in ids and "meth-sync-simple" in ids), "conflicto no resuelto"
    eng.feedback(agent, True, 0.9)
    assert all(0 <= c.performance_score <= 1 for c in eng.library.values())
    print("SELFTEST OK ->", ids)


def main():
    ap = argparse.ArgumentParser(description="MOSAIC privado (monolítico).")
    ap.add_argument("request", nargs="?", help="petición en lenguaje natural")
    ap.add_argument("--offline", action="store_true", help="sin red (mock + hashing)")
    ap.add_argument("--fast", action="store_true", help="usa el endpoint rápido (13B)")
    ap.add_argument("--no-exec", action="store_true", help="solo compone, no ejecuta")
    ap.add_argument("--feedback", choices=["ok", "fail"], help="aplica feedback tras ejecutar")
    ap.add_argument("--out", metavar="RUTA", help="guarda un registro JSON de la ejecución (o carpeta en --aprender)")
    ap.add_argument("--evaluar", metavar="CARPETA", help="el modelo evalúa los .json de una carpeta")
    ap.add_argument("--analizar", metavar="CARPETA", help="el modelo analiza el aprendizaje.md de una tanda")
    ap.add_argument("--aprender", action="store_true",
                    help="bucle de aprendizaje: compone, ejecuta, se autojuzga y realimenta")
    ap.add_argument("--ciclos", type=int, default=1, help="pasadas sobre el conjunto de peticiones (--aprender)")
    ap.add_argument("--peticiones", metavar="ARCHIVO", help="archivo con una petición por línea (--aprender)")
    ap.add_argument("--pipeline", action="store_true", help="C2: el principal ejecuta mientras el juez valora la anterior (con MOSAIC_WORKERS>1, pool de bocas)")
    ap.add_argument("--ab", metavar="raw|URL", help="C3: A/B composición vs 'raw' (sin MOSAIC) o vs otro modelo")
    ap.add_argument("--podar", action="store_true", help="poda por redundancia (archiva casi-duplicados) y guarda")
    ap.add_argument("--umbral", type=float, default=0.85, help="umbral de similitud coseno para podar")
    ap.add_argument("--consolidar", action="store_true",
                    help="aprende del USO REAL: juzga y realimenta lo registrado por mosaic.sh")
    ap.add_argument("--generar-capacidades", action="store_true", help="P2-5: genera capacidades desde los huecos")
    ap.add_argument("--curar-existentes", action="store_true", help="el juez puntúa las auto-generadas y descarta las flojas")
    ap.add_argument("--entrenar-predictor", action="store_true", help="P2-6: entrena el predictor de tokens")
    ap.add_argument("--entrenar-reward", action="store_true", help="P3-7: entrena el reward model")
    ap.add_argument("--server", action="store_true", help="P4-9: servidor OpenAI-compatible")
    ap.add_argument("--port", type=int, default=8077, help="puerto del servidor (--server)")
    ap.add_argument("--selftest", action="store_true", help="prueba interna offline")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if args.evaluar:
        evaluar(args.evaluar, offline=args.offline)
        return
    if args.analizar:
        analizar(args.analizar, offline=args.offline)
        return
    if args.aprender:
        aprender(ciclos=args.ciclos, peticiones_file=args.peticiones,
                 offline=args.offline, fast=args.fast, out=args.out,
                 pipeline=args.pipeline, ab=args.ab)
        return
    if args.podar:
        eng = make_engine(offline=True, fast=False)   # poda no necesita LLM ni red
        arch, resc = eng.podar_redundantes(umbral=args.umbral)
        state = os.getenv("MOSAIC_STATE", "data/state.json")
        eng.save_state(state)
        print(f"Poda (umbral {args.umbral}) -> archivadas: {len(arch)} | rescatadas: {len(resc)}")
        for vid, kid, sim in arch:
            print(f"  - {vid}  ≈ {kid}  (sim {sim})")
        for rid, dom in resc:
            print(f"  + rescatada {rid}  (dominio '{dom}')")
        return
    if args.consolidar:
        consolidar(offline=args.offline, out=args.out)
        return
    if args.generar_capacidades:
        generar_capacidades(offline=args.offline, out=args.out)
        return
    if args.curar_existentes:
        curar_existentes(offline=args.offline, out=args.out)
        return
    if args.entrenar_predictor:
        entrenar_predictor(out=args.out)
        return
    if args.entrenar_reward:
        entrenar_reward(out=args.out)
        return
    if args.server:
        servidor(port=args.port, offline=args.offline)
        return
    if not args.request:
        ap.print_help()
        return

    eng = make_engine(args.offline, args.fast)
    intent, agent = eng.compose(args.request)

    print("=" * 70)
    print("PETICIÓN  :", args.request)
    print("OBJETIVO  :", intent.goal)
    print("DOMINIOS  :", intent.domains, "| complejidad:", intent.complexity)
    print("COMPUESTO :", [c.id for c in agent.caps], f"({agent.total_tokens} tokens)")
    if agent.crag:
        _cq = agent.crag.get("quality")
        _hueco = " ⚠️ HUECO (ninguna capacidad encaja bien)" if agent.crag.get("gap") else ""
        print(f"CRAG      : calidad={_cq} acción={agent.crag.get('action')}{_hueco}")
    print("=" * 70)
    print(agent.prompt)
    print("=" * 70)

    output, error = None, None
    if not args.no_exec:
        try:
            output = eng.execute(agent)
            print("RESPUESTA DEL MODELO:\n")
            print(output)
        except Exception as e:
            error = str(e)
            log(f"No se pudo ejecutar contra el modelo ({e}). Prueba --offline o revisa el cluster.")

    _log_historial(args.request, agent, output, error, getattr(eng, "last_metrics", {}))   # uso real -> cola

    if args.feedback:
        eng.feedback(agent, args.feedback == "ok", 0.9)
        state = os.getenv("MOSAIC_STATE", "")
        if state:
            eng.save_state(state)
            log(f"Estado actualizado en {state}")

    if args.out:
        rec = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "request": args.request,
            "offline": args.offline, "fast": args.fast,
            "endpoint": endpoint_for(args.offline, args.fast) or "mock",
            "model": os.getenv("MOSAIC_LLM_MODEL", "local-model"),
            "intent": {"goal": intent.goal, "domains": intent.domains,
                       "complexity": intent.complexity},
            "composed": [c.id for c in agent.caps],
            "tokens": agent.total_tokens,
            "prompt": agent.prompt,
            "output": output,
            "error": error,
            # 💰 F2 economía (ronda bursátil 5-jul): el COSTE real de esta ejecución viaja
            #    en el registro — tokens del campo usage de llama-server (P1-3), no estimados.
            "usage": (getattr(eng, "last_metrics", {}) or {}).get("usage", {}),
            "latency_s": (getattr(eng, "last_metrics", {}) or {}).get("latency_s", 0.0),
            "ejecutor": (getattr(eng, "last_metrics", {}) or {}).get("ejecutor", ""),
        }
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
        log(f"Registro -> {args.out}")


if __name__ == "__main__":
    main()
