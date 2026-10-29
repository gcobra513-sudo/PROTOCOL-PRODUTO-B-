"""
Sobe o servidor. `python3 -m servidor`.

Em desenvolvimento:

    PROTOCOL_MODO_ENSAIO=1 python3 -m servidor --recarregar

Em produção, nada de modo ensaio e nada de segredo padrão:

    export PROTOCOL_SEGREDO="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
    export PROTOCOL_RAIZ=/var/lib/protocol
    export PROTOCOL_ORIGENS=https://portal.exemplo.org
    export PROTOCOL_SMTP_HOST=smtp.exemplo.org
    export PROTOCOL_SMTP_REMETENTE=portal@exemplo.org
    python3 -m servidor --porta 8000
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import ConfiguracaoInvalida, carregar


def main(argumentos: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="servidor", description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--porta", type=int, default=8000)
    p.add_argument("--recarregar", action="store_true")
    args = p.parse_args(argumentos)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        cfg = carregar()
    except ConfiguracaoInvalida as e:
        # Mensagem inteira no stderr, não um traceback: quem sobe o servidor
        # precisa saber o que exportar, não onde a exceção nasceu.
        print(f"\nNÃO SUBI:\n\n{e}\n", file=sys.stderr)
        return 2

    import uvicorn

    if args.recarregar:
        uvicorn.run(
            "servidor.app:criar_app",
            factory=True,
            host=args.host,
            port=args.porta,
            reload=True,
        )
        return 0

    from .app import criar_app

    uvicorn.run(criar_app(cfg), host=args.host, port=args.porta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
