import json
import pathlib

import docutils.nodes
import yaml
from sphinx.builders.text import TextBuilder
from sphinx.util.logging import getLogger
from sphinx.writers.text import TextTranslator

from .writer import Rewriter, TextRenderer

logger = getLogger(__name__)


class FallbackTextTranslator(TextTranslator):
    def unknown_visit(self, node):
        # Ignore unknown nodes
        logger.warning("Skip unknown node: %s", node.__class__.__name__)

    def unknown_departure(self, node):
        # Ignore unknown nodes
        pass


class SimpleMarkdownBuilder(TextBuilder):
    """Simple markdown builder. Piggy-backs on the text builder by rewriting
    some parts of the doctree before the build."""

    # These are used by the parent class implementation of builder methods
    # - 'name' sets the output directory
    # - 'out_suffix' sets the file extension (added to {outdir}/{docname})
    # - 'format' should stay as set by the parent (in this case, 'text') as
    #   it affects custom node type registration for builders and translators

    name = "markdown"
    out_suffix = ".md"
    default_translator_class = FallbackTextTranslator

    def __init__(self, app, env):
        super().__init__(app, env)
        self.text_renderer = TextRenderer(app, env)
        self._include_header = app.config.markdown_include_header

    def init(self):
        super().init()
        self.text_renderer.init()

    def get_header_data(self, docname, doctree):
        # FIXME should this also follow ManifestMixin.get_title?
        title_node = doctree.next_node(docutils.nodes.title)
        title = title_node.astext() if title_node else None
        url = f"{self._metadata_base_url}/{docname}.md"
        return dict(title=title, url=url)

    def format_header(self, docname, doctree):
        header_data = self.get_header_data(docname, doctree)
        return "".join(
            [
                "---\n",
                yaml.safe_dump(header_data),
                "---\n",
            ]
        )

    def prepare_writing(self, docnames):
        super().prepare_writing(docnames)
        self.text_renderer.prepare_writing(docnames)

    def write_doc(self, docname, doctree):
        if self._include_header:
            header = self.format_header(docname, doctree)
        else:
            header = None
        rewriter = Rewriter(doctree, text_renderer=self.text_renderer, header=header)
        doctree.walkabout(rewriter)
        super().write_doc(docname, doctree)


class ManifestMixin:

    def __init__(self, app, env):
        super().__init__(app, env)
        self._metadata_base_url = app.config.html_baseurl.rstrip("/")
        self._include_metadata = app.config.markdown_include_metadata
        self._use_title_attribute = app.config.metadata_use_title_attribute

    def get_title(self, doctree):
        split_title = doctree.attributes.get("split_title")
        if split_title:
            return split_title
        meta_title = doctree.attributes.get("title")
        if meta_title and self._use_title_attribute:
            return meta_title
        else:
            title_node = doctree.next_node(docutils.nodes.title)
            return title_node.astext() if title_node else None

    def get_url(self, docname, doctree):
        # A split document points at its original page, with an anchor
        docname = doctree.attributes.get("split_docname", docname)
        url = f"{self._metadata_base_url}/{docname}.html"
        anchor = doctree.attributes.get("split_anchor")
        return f"{url}#{anchor}" if anchor else url

    def create_metadata(self, docname, doctree):
        title = self.get_title(doctree)
        url = self.get_url(docname, doctree)
        return {
            "metadataAttributes": {
                "title": {
                    "value": {
                        "type": "STRING",
                        "stringValue": title,
                    },
                    "includeForEmbedding": True,
                },
                "x-amz-bedrock-kb-source-uri": {
                    "value": {
                        "type": "STRING",
                        "stringValue": url,
                    },
                    "includeForEmbedding": True,
                },
            }
        }

    def metadata_target(self, docname):
        outdir = pathlib.Path(self.outdir)
        content_file = outdir / f"{docname}{self.out_suffix}"
        metadata_file = outdir / f"{docname}{self.out_suffix}.metadata.json"
        assert content_file.exists()
        return metadata_file

    def write_doc(self, docname: str, doctree: docutils.nodes.Node) -> None:
        # Before the markdown builder modifies the tree, find the document
        # title and create the metadata
        if self._include_metadata:
            metadata = self.create_metadata(docname, doctree)

        # Call the markdown builder to create the content file
        super().write_doc(docname, doctree)

        # Finally, write metadata file
        if self._include_metadata:
            with self.metadata_target(docname).open("w") as outfile:
                json.dump(metadata, outfile, indent=4, sort_keys=True)


class SplitMixin:
    """Write one output document per sub-section of a page. The parts are
    named {docname}__{anchor} and carry the information needed to point back
    at the sub-section of the original page (see ManifestMixin)."""

    def __init__(self, app, env):
        super().__init__(app, env)
        self._split_sections = app.config.markdown_split_sections
        self._split_leadin_limit = app.config.markdown_split_leadin_limit

    @staticmethod
    def child_sections(section):
        return [c for c in section.children if isinstance(c, docutils.nodes.section)]

    def split_doctree(self, docname, doctree):
        """Return a list of (docname, doctree) parts, or None if this document
        should be written as a single file. Only a document with exactly one
        top level section, whose child sections all have an id, is split."""
        top_sections = [
            c for c in doctree.children if isinstance(c, docutils.nodes.section)
        ]
        if len(top_sections) != 1:
            return None
        children = self.child_sections(top_sections[0])
        if not children or any(not child["ids"] for child in children):
            return None

        # With many sections the shared lead-in would be a near-duplicate
        # wall of text in every part, so keep only the page title
        keep_leadin = len(children) <= self._split_leadin_limit

        parts = []
        for child in children:
            anchor = child["ids"][0]
            part = doctree.deepcopy()
            part_top = part.next_node(docutils.nodes.section)
            part_title = part_top.next_node(docutils.nodes.title)
            part_top.children = [
                c
                for c in part_top.children
                if c is part_title
                or (keep_leadin and not isinstance(c, docutils.nodes.section))
                or (isinstance(c, docutils.nodes.section) and c["ids"] == child["ids"])
            ]
            title_node = child.next_node(docutils.nodes.title)
            part.attributes["split_docname"] = docname
            part.attributes["split_anchor"] = anchor
            part.attributes["split_title"] = (
                title_node.astext() if title_node else None
            ) or part_title.astext()
            parts.append((f"{docname}__{anchor}", part))
        return parts

    def write_doc(self, docname, doctree):
        parts = self.split_doctree(docname, doctree) if self._split_sections else None
        if parts is None:
            super().write_doc(docname, doctree)
        else:
            for part_docname, part in parts:
                super().write_doc(part_docname, part)


class MarkdownBuilder(SplitMixin, ManifestMixin, SimpleMarkdownBuilder):
    pass
