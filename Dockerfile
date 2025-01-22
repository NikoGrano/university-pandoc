FROM pandoc/latex:latest

RUN apk add --no-cache --quiet \
          font-linux-libertine \
          qpdf \
          biber && \
    tlmgr install \
          extsizes \
          lastpage \
          biblatex \
          biblatex-apa \
          framed \
          fancyvrb \
          listings \
          tcolorbox \
          pgf \
          environ \
          trimspaces \
          footmisc \
          biblatex-sbl \
          biblatex-chicago \
          xstring

WORKDIR /workdir
