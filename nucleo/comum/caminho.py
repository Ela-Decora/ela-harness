"""Caminho de import do núcleo: põe as três pastas do núcleo no `sys.path`, na ordem comum, planejamento e
desenvolvimento. É o único módulo que conhece as três pastas; quem roda o núcleo o chama antes dos outros imports."""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ_DO_PLUGIN: Path = Path(__file__).resolve().parents[2]
PASTAS_DO_NUCLEO: tuple[str, ...] = ("comum", "planejamento", "desenvolvimento")


def no_caminho() -> None:
    """Põe `<raiz do plugin>/nucleo/<pasta>` no começo do `sys.path`, na ordem de `PASTAS_DO_NUCLEO`. A pasta que já
    está no caminho sai de onde estava e entra na posição dela, sem repetir."""
    pastas = [str(RAIZ_DO_PLUGIN / "nucleo" / pasta) for pasta in PASTAS_DO_NUCLEO]
    sys.path[:] = pastas + [item for item in sys.path if item not in pastas]
