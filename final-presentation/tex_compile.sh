#!/bin/sh
pandoc --to=beamer --include-in-header=./header.tex -o slides.tex -s --pdf-engine=pdflatex slides.md
sed -i 's/^.*newenv.*Shaded.*$/\\newenvironment{Shaded}{\\scriptsize}{}/' slides.tex
pdflatex slides.tex
rm slides.aux slides.log slides.nav slides.snm slides.toc slides.vrb slides.tex
vim slides.md
