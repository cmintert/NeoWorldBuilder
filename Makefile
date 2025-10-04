# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= python3 -m sphinx
SPHINXAPIDOC  ?= python3 -m sphinx.ext.apidoc
SOURCEDIR     = source
BUILDDIR      = build
SRCDIR        = src

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile clean-api apidoc clean-html rebuild

# Clean auto-generated API documentation
clean-api:
	rm -rf $(SOURCEDIR)/api/

# Generate API documentation from source code
apidoc: clean-api
	$(SPHINXAPIDOC) -f -o $(SOURCEDIR)/api $(SRCDIR) --separate --module-first
	@echo "API documentation generated in $(SOURCEDIR)/api/"

# Clean HTML build
clean-html:
	rm -rf $(BUILDDIR)/html

# Rebuild everything from scratch
rebuild: clean-api clean-html
	$(SPHINXAPIDOC) -f -o $(SOURCEDIR)/api $(SRCDIR) --separate --module-first
	@$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@echo "Documentation rebuilt from scratch in $(BUILDDIR)/html/"

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
