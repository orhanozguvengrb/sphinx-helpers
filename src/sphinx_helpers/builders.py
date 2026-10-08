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
    """Write one output document per sub-section of a page, at any depth. The
    parts are named {docname}__{anchor} and carry the information needed to
    point back at the sub-section of the original page (see ManifestMixin).

    The page itself is a part too, written as {docname} with the url of the
    page: its title and its own content.

    A part holds the sections leading to the sub-section (the page, then each
    parent in turn) with their own content, and the sub-section itself with
    its own content: h1 + h2 + h3 for an h3. The content of the child sections
    of the sub-section, and of sibling sections, is left to their own parts.
    A parent with many sub-sections (more than markdown_split_leadin_limit)
    would have its content repeated in every one of their parts, so for such a
    parent only the title is kept."""

    def __init__(self, app, env):
        super().__init__(app, env)
        self._split_sections = app.config.markdown_split_sections
        self._split_leadin_limit = app.config.markdown_split_leadin_limit

    @staticmethod
    def child_sections(section):
        return [c for c in section.children if isinstance(c, docutils.nodes.section)]

    @staticmethod
    def own_content(section):
        return [
            c
            for c in section.children
            if not isinstance(c, (docutils.nodes.section, docutils.nodes.title))
        ]

    def descendants(self, section, chain=()):
        """Yield (chain, section) for every section below the given one, where
        chain is the sections leading to it, starting with the given one."""
        chain = chain + (section,)
        for child in self.child_sections(section):
            yield chain, child
            yield from self.descendants(child, chain)

    def split_doctree(self, docname, doctree):
        """Return a list of (docname, doctree) parts, or None if this document
        should be written as a single file. Only a document with exactly one
        top level section, whose sub-sections all have an id, is split."""
        top_sections = [
            c for c in doctree.children if isinstance(c, docutils.nodes.section)
        ]
        if len(top_sections) != 1:
            return None
        found = list(self.descendants(top_sections[0]))
        if not found or any(not section["ids"] for _, section in found):
            return None

        # A section with no content of its own (only sub-sections) is left out
        found = [(c, s) for c, s in found if self.own_content(s)]
        if not found:
            return None

        # The page itself is a part too (its title and own content), so every
        # section has exactly one file and the lead-in is not lost
        top = top_sections[0]
        if self.own_content(top):
            found.insert(0, ((), top))

        def locate(tree, section):
            return tree.next_node(
                lambda n: isinstance(n, docutils.nodes.section)
                and n["ids"][:1] == section["ids"][:1]
            )

        parts = []
        for chain, section in found:
            part = doctree.deepcopy()
            path = [part.next_node(docutils.nodes.section)]
            if chain:
                path += [locate(part, s) for s in chain[1:] + (section,)]

            # Sections leading to the sub-section keep their own content, or
            # only their title if they have many sub-sections. The sub-section
            # keeps its own content. (chain holds the original parents.)
            for parent, node, next_node in zip(chain, path, path[1:]):
                title = node.next_node(docutils.nodes.title)
                few = len(self.child_sections(parent)) <= self._split_leadin_limit
                context = self.own_content(node) if few else []
                node.children = [title, *context, next_node]
            path[-1].children = [
                c
                for c in path[-1].children
                if not isinstance(c, docutils.nodes.section)
            ]

            title_node = section.next_node(docutils.nodes.title)
            part_title = path[0].next_node(docutils.nodes.title)
            part.attributes["split_docname"] = docname
            part.attributes["split_title"] = (
                title_node.astext() if title_node else None
            ) or part_title.astext()
            if chain:
                part.attributes["split_anchor"] = section["ids"][0]
                parts.append((f"{docname}__{section['ids'][0]}", part))
            else:
                parts.append((docname, part))
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
