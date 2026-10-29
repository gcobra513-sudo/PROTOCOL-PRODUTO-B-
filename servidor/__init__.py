"""
O servidor do portal: recebe o cadastro do filiado e devolve o veredicto.

POR QUE ESTE ARQUIVO MEXE NO sys.path

O servidor importa `nucleo.processo_cnj` para conferir o número do processo —
a MESMA implementação que o motor usa, de propósito: duas validações do
dígito verificador em lugares diferentes é a receita para elas divergirem no
dia em que uma for corrigida.

`nucleo` mora na raiz do repositório, que não está no caminho de importação
quando o servidor sobe sozinho num provedor — lá o diretório de trabalho é
outro. Sem isto, a implantação quebra no primeiro `import`, e quebra no ar,
não aqui.

A alternativa correta a prazo é instalar o pacote (`pip install -e .`). Até
lá, isto é explícito e não esconde nada.
"""

import sys as _sys
from pathlib import Path as _Path

_RAIZ = _Path(__file__).resolve().parent.parent
if (_RAIZ / "nucleo").is_dir() and str(_RAIZ) not in _sys.path:
    _sys.path.insert(0, str(_RAIZ))
