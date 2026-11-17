# A DEMONSTRAÇÃO HOSPEDADA — um link para mostrar o produto numa reunião.
#
# NÃO É A IMPLANTAÇÃO. O sistema de verdade vai para uma máquina em São
# Paulo, pelo passo a passo de `implantacao/LEIAME.md`. Isto aqui roda
# `ferramentas/demo.py`: modo ensaio, só cadastro declaradamente fictício,
# banco dentro do próprio contêiner. Reiniciou, nasce de novo do zero — e por
# isso pode morar num plano gratuito, em qualquer região: não há dado de
# ninguém aqui dentro.
#
#   docker build -f implantacao/demo/Dockerfile -t protocol-demo .
#   docker run -p 8080:8080 protocol-demo

# ---- o portal é compilado aqui, e o Node não segue para a imagem final
FROM node:22-bookworm-slim AS portal
WORKDIR /app
COPY compartilhado/ compartilhado/
COPY portal/package.json portal/package-lock.json portal/
RUN cd portal && npm ci
COPY portal/ portal/
# A API em "/": portal e API saem do mesmo endereço.
RUN cd portal && VITE_API=/ npx vite build --outDir /portal-pronto --emptyOutDir

FROM python:3.13-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# A TRAVA, com as impressões digitais: a imagem instala as mesmas versões
# que a suíte testou, e nada que não confira com a impressão.
COPY requirements.lock requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY . .
COPY --from=portal /portal-pronto /portal-pronto
# USUÁRIO COMUM: o PostgreSQL se recusa a rodar como root, e a demonstração
# não precisa de privilégio nenhum.
RUN useradd --create-home demo
USER demo
ENV PORT=8080
EXPOSE 8080
# 0.0.0.0 porque quem chega é o roteador da hospedagem, de fora do contêiner.
CMD ["sh", "-c", "exec python ferramentas/demo.py --host 0.0.0.0 --porta ${PORT} --portal-pronto /portal-pronto"]
