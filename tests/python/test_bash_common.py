"""
Tests para lib/bash-common.sh — verifican funciones de la librería compartida.
Ejecutar: pytest tests/python/ -v
"""
import subprocess
import os
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMMON_LIB = os.path.join(REPO_ROOT, "lib", "bash-common.sh")


def run_bash(script: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Helper: ejecutar un snippet bash que sourcea bash-common.sh."""
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True, text=True, timeout=10, env=full_env,
    )


class TestSanitizePath:
    """sanitize_path() debe rechazar caracteres peligrosos."""

    def test_valid_path(self):
        r = run_bash(f'source "{COMMON_LIB}"; sanitize_path "/tmp/test" "test"')
        assert r.returncode == 0
        assert "/tmp/test" in r.stdout

    def test_rejects_semicolon(self):
        r = run_bash(f'source "{COMMON_LIB}"; sanitize_path "/tmp/test;rm -rf /" "bad"')
        assert r.returncode != 0

    def test_rejects_backtick(self):
        r = run_bash(f'source "{COMMON_LIB}"; sanitize_path "/tmp/`whoami`" "bad"')
        assert r.returncode != 0

    def test_rejects_empty(self):
        r = run_bash(f'source "{COMMON_LIB}"; sanitize_path "" "empty"')
        assert r.returncode != 0

    def test_rejects_dollar(self):
        r = run_bash(f"source \"{COMMON_LIB}\"; sanitize_path '/tmp/$HOME' 'bad'")
        assert r.returncode != 0


class TestSanitizeInteger:
    """sanitize_integer() debe aceptar solo enteros positivos."""

    def test_valid_integer(self):
        r = run_bash(f'source "{COMMON_LIB}"; sanitize_integer "42" "count"')
        assert r.returncode == 0
        assert "42" in r.stdout

    def test_rejects_letters(self):
        r = run_bash(f'source "{COMMON_LIB}"; sanitize_integer "abc" "count"')
        assert r.returncode != 0

    def test_rejects_negative(self):
        r = run_bash(f'source "{COMMON_LIB}"; sanitize_integer "-5" "count"')
        assert r.returncode != 0

    def test_rejects_float(self):
        r = run_bash(f'source "{COMMON_LIB}"; sanitize_integer "3.14" "count"')
        assert r.returncode != 0


class TestRotateLog:
    """rotate_log() debe rotar archivos que excedan max_lines."""

    def test_no_rotation_under_limit(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("line\n" * 50)
            f.flush()
            r = run_bash(f'source "{COMMON_LIB}"; rotate_log "{f.name}" 100')
            assert r.returncode == 0
            assert os.path.exists(f.name)
            assert not os.path.exists(f"{f.name}.1")
            os.unlink(f.name)

    def test_rotation_over_limit(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("line\n" * 200)
            f.flush()
            r = run_bash(f'source "{COMMON_LIB}"; rotate_log "{f.name}" 100')
            assert r.returncode == 0
            assert os.path.exists(f"{f.name}.1")
            # Original debe estar vacío o recién creado
            with open(f.name) as check:
                assert len(check.readlines()) < 10
            os.unlink(f.name)
            os.unlink(f"{f.name}.1")


class TestVerifySha256:
    """verify_sha256() debe detectar hashes incorrectos."""

    def test_placeholder_hash_skips(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".bin", delete=False) as f:
            f.write("test data")
            f.flush()
            r = run_bash(
                f'source "{COMMON_LIB}"; verify_sha256 "{f.name}" "REPLACE_WITH_ACTUAL_SHA256_HASH"'
            )
            assert r.returncode == 0
            os.unlink(f.name)

    def test_correct_hash_passes(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".bin", delete=False) as f:
            f.write("hello world")
            f.flush()
            # Calcular hash real
            import hashlib
            expected = hashlib.sha256(b"hello world").hexdigest()
            r = run_bash(f'source "{COMMON_LIB}"; verify_sha256 "{f.name}" "{expected}"')
            assert r.returncode == 0
            os.unlink(f.name)

    def test_wrong_hash_fails(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".bin", delete=False) as f:
            f.write("hello world")
            f.flush()
            r = run_bash(f'source "{COMMON_LIB}"; verify_sha256 "{f.name}" "badhash123"')
            assert r.returncode != 0
            # File should be deleted on mismatch
            assert not os.path.exists(f.name)


class TestColorFunctions:
    """info/ok/warn/error deben ejecutar sin errores."""

    def test_info(self):
        r = run_bash(f'source "{COMMON_LIB}"; info "test message"')
        assert r.returncode == 0
        assert "test message" in r.stdout

    def test_ok(self):
        r = run_bash(f'source "{COMMON_LIB}"; ok "success"')
        assert r.returncode == 0

    def test_warn(self):
        r = run_bash(f'source "{COMMON_LIB}"; warn "warning"')
        assert r.returncode == 0

    def test_error(self):
        r = run_bash(f'source "{COMMON_LIB}"; error "error"')
        assert r.returncode == 0

    def test_die(self):
        r = run_bash(f'source "{COMMON_LIB}"; die "fatal"')
        assert r.returncode != 0
