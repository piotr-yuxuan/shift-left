# basedpyright-lsp

Runs `basedpyright-langserver --stdio` (from PATH) for `.py` and `.pyi` files, so
Claude Code receives type diagnostics after each edit and can navigate by symbol.
basedpyright reads `pyrightconfig.json`, `[tool.basedpyright]` and `[tool.pyright]`.
Do not enable `pyright-lsp` at the same time, or diagnostics are reported twice.
