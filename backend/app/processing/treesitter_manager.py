"""
Tree-sitter Language and Parser management.
Supports Python, JavaScript, TypeScript (and TSX), Java, C, C++, and Go,
with an extensible architecture to easily add additional languages.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Callable, Any
import tree_sitter

logger = logging.getLogger(__name__)


class LanguageManager:
    """
    Thread-safe registry for Tree-sitter Language grammars and Parser instances.
    """

    def __init__(self) -> None:
        self._languages: Dict[str, tree_sitter.Language] = {}
        self._extension_map: Dict[str, str] = {}
        self._initialized: bool = False
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Initialize grammars for the 7 primary languages."""
        if self._initialized:
            return

        try:
            import tree_sitter_python
            self.register_language(
                "python",
                lambda: tree_sitter.Language(tree_sitter_python.language()),
                [".py", ".pyw", ".pyi"]
            )
        except Exception as e:
            logger.warning(f"Failed to load tree-sitter-python: {e}")

        try:
            import tree_sitter_javascript
            self.register_language(
                "javascript",
                lambda: tree_sitter.Language(tree_sitter_javascript.language()),
                [".js", ".mjs", ".cjs"]
            )
        except Exception as e:
            logger.warning(f"Failed to load tree-sitter-javascript: {e}")

        try:
            import tree_sitter_typescript
            self.register_language(
                "typescript",
                lambda: tree_sitter.Language(tree_sitter_typescript.language_typescript()),
                [".ts", ".mts", ".cts"]
            )
            self.register_language(
                "tsx",
                lambda: tree_sitter.Language(tree_sitter_typescript.language_tsx()),
                [".tsx", ".jsx"]
            )
        except Exception as e:
            logger.warning(f"Failed to load tree-sitter-typescript: {e}")

        try:
            import tree_sitter_java
            self.register_language(
                "java",
                lambda: tree_sitter.Language(tree_sitter_java.language()),
                [".java"]
            )
        except Exception as e:
            logger.warning(f"Failed to load tree-sitter-java: {e}")

        try:
            import tree_sitter_c
            self.register_language(
                "c",
                lambda: tree_sitter.Language(tree_sitter_c.language()),
                [".c", ".h"]
            )
        except Exception as e:
            logger.warning(f"Failed to load tree-sitter-c: {e}")

        try:
            import tree_sitter_cpp
            self.register_language(
                "cpp",
                lambda: tree_sitter.Language(tree_sitter_cpp.language()),
                [".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".tpp"]
            )
        except Exception as e:
            logger.warning(f"Failed to load tree-sitter-cpp: {e}")

        try:
            import tree_sitter_go
            self.register_language(
                "go",
                lambda: tree_sitter.Language(tree_sitter_go.language()),
                [".go"]
            )
        except Exception as e:
            logger.warning(f"Failed to load tree-sitter-go: {e}")

        self._initialized = True

    def register_language(
        self,
        name: str,
        loader: Callable[[], tree_sitter.Language],
        extensions: list[str],
    ) -> None:
        """Register a new language grammar and its associated file extensions."""
        norm_name = name.lower()
        try:
            lang_obj = loader()
            self._languages[norm_name] = lang_obj
            for ext in extensions:
                norm_ext = ext.lower()
                if not norm_ext.startswith("."):
                    norm_ext = f".{norm_ext}"
                self._extension_map[norm_ext] = norm_name
            logger.debug(f"Registered tree-sitter language '{norm_name}' for {extensions}")
        except Exception as e:
            logger.error(f"Error registering language '{norm_name}': {e}")

    def get_language(self, language_name: str) -> Optional[tree_sitter.Language]:
        """Get the tree-sitter Language object by language name."""
        return self._languages.get(language_name.lower())

    def get_language_for_extension(self, extension: str) -> Optional[str]:
        """Return the canonical language identifier for a file extension."""
        norm_ext = extension.lower()
        if not norm_ext.startswith("."):
            norm_ext = f".{norm_ext}"
        return self._extension_map.get(norm_ext)

    def is_supported_file(self, file_path: str | Path) -> bool:
        """Check if a file path is supported by the Tree-sitter parser registry."""
        suffix = Path(file_path).suffix.lower()
        return suffix in self._extension_map

    def get_parser(self, language_name: str) -> Optional[tree_sitter.Parser]:
        """Get a configured Tree-sitter Parser instance for the specified language."""
        lang = self.get_language(language_name)
        if not lang:
            return None
        return tree_sitter.Parser(lang)

    def parse_source(
        self,
        source_bytes: bytes,
        language_name: str,
        max_bytes: int = 1_000_000,
    ) -> Optional[tree_sitter.Tree]:
        """
        Safely parse source code bytes into a Tree-sitter AST Tree.
        Returns None if language is unsupported or source exceeds safety limits.
        """
        if len(source_bytes) > max_bytes:
            logger.warning(f"Source size ({len(source_bytes)} bytes) exceeds max limit ({max_bytes} bytes). Skipping.")
            return None

        parser = self.get_parser(language_name)
        if not parser:
            logger.warning(f"No parser available for language: {language_name}")
            return None

        try:
            tree = parser.parse(source_bytes)
            return tree
        except Exception as e:
            logger.error(f"Tree-sitter parse error for language '{language_name}': {e}")
            return None


# Global singleton instance
language_manager = LanguageManager()

