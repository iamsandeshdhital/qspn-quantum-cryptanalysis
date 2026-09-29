# Build the report.  Three pdflatex passes are required: the first writes the
# .aux file, bibtex turns that into .bbl, and the last two settle the citations
# and then the cross-references and table of contents that shift once the
# bibliography changes the pagination.
#
# The generated inputs (results_generated.tex and the three table files) come
# from the experiment records, so `make` regenerates them first -- the report
# can never quote a number that is not in results/data/.

TEX      := pdflatex -interaction=nonstopmode
BIB      := bibtex
ROOT     := ../..
PYTHON   ?= python
GENERATED := results_generated.tex table_b_sweep.tex table_d_threshold.tex table_e_resources.tex

.PHONY: all clean distclean macros

all: report.pdf

macros $(GENERATED):
	$(PYTHON) $(ROOT)/scripts/make_report_macros.py

report.pdf: report.tex references.bib $(GENERATED)
	$(TEX) report.tex
	$(BIB) report
	$(TEX) report.tex
	$(TEX) report.tex
	@echo "built: $@"

clean:
	rm -f *.aux *.bbl *.blg *.log *.out *.toc *.synctex.gz *.fls *.fdb_latexmk

distclean: clean
	rm -f report.pdf $(GENERATED)
