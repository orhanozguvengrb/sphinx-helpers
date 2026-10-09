import hashlib
import json
import pathlib
import re

import docutils.nodes
import yaml
from sphinx import addnodes
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

    A sub-section is a section, or an object description with an anchor (a
    function, class or method documented with a domain directive such as
    c:function), which can be nested in another one.

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

    # Nodes that are not rendered, so they are not content by themselves
    invisible = (
        addnodes.index,
        docutils.nodes.target,
        docutils.nodes.comment,
        docutils.nodes.substitution_definition,
    )

    @staticmethod
    def part_name(docname, anchor, used):
        """The name of the output document of a sub-section: {docname}__{anchor},
        made safe to use as a file name. Anchors can hold characters that are
        not allowed in a file name everywhere (for example "*" in an operator),
        be very long, or differ only in case (C++ operators). Then the name is
        cleaned up and ends with a short hash of the anchor, which keeps it
        unique. The anchor itself is kept as it is in the url."""
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", anchor)[:100]
        name = f"{docname}__{safe}"
        if safe != anchor or name.lower() in used:
            name += "-" + hashlib.sha1(anchor.encode()).hexdigest()[:8]
        used.add(name.lower())
        return name

    @staticmethod
    def signatures(node):
        return [c for c in node.children if isinstance(c, addnodes.desc_signature)]

    def unit_id(self, node):
        """The anchor of a section, or of an object description"""
        if isinstance(node, addnodes.desc):
            signatures = self.signatures(node)
            ids = signatures[0]["ids"] if signatures else []
        else:
            ids = node["ids"]
        return ids[0] if ids else None

    def is_unit(self, node):
        if isinstance(node, docutils.nodes.section):
            return True
        # An object description without an anchor stays part of its parent
        return isinstance(node, addnodes.desc) and self.unit_id(node) is not None

    @staticmethod
    def container(node):
        """The node holding the content (and child units) of a unit"""
        if isinstance(node, addnodes.desc):
            for child in node.children:
                if isinstance(child, addnodes.desc_content):
                    return child
            return None
        return node

    def child_units(self, node):
        container = self.container(node)
        children = container.children if container is not None else []
        return [c for c in children if self.is_unit(c)]

    def own_content(self, node):
        container = self.container(node)
        children = container.children if container is not None else []
        return [
            c
            for c in children
            if not self.is_unit(c)
            and not isinstance(c, (docutils.nodes.title, *self.invisible))
        ]

    def unit_title(self, node):
        if isinstance(node, addnodes.desc):
            signature = self.signatures(node)[0]
            parts = [
                signature.next_node(addnodes.desc_addname),
                signature.next_node(addnodes.desc_name),
            ]
            title = "".join(p.astext() for p in parts if p is not None)
            return title or signature.astext()
        title_node = node.next_node(docutils.nodes.title)
        return title_node.astext() if title_node else None

    def rebuild(self, node, content):
        """Keep the heading of a unit (its title or signatures) and replace
        its content"""
        container = self.container(node)
        if isinstance(node, addnodes.desc):
            heading = self.signatures(node)
            if container is not None:
                container.children = content
            node.children = heading + ([container] if container is not None else [])
        else:
            node.children = [node.next_node(docutils.nodes.title), *content]

    def descendants(self, unit, chain=()):
        """Yield (chain, unit) for every unit below the given one, where chain
        is the units leading to it, starting with the given one."""
        chain = chain + (unit,)
        for child in self.child_units(unit):
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
        if not found or any(self.unit_id(unit) is None for _, unit in found):
            return None

        # A unit with no content of its own (only sub-sections) is left out
        found = [(c, u) for c, u in found if self.own_content(u)]
        if not found:
            return None

        # The page itself is a part too (its title and own content), so every
        # section has exactly one file and the lead-in is not lost
        top = top_sections[0]
        if self.own_content(top):
            found.insert(0, ((), top))

        def locate(tree, unit):
            return tree.next_node(
                lambda n: self.is_unit(n) and self.unit_id(n) == self.unit_id(unit)
            )

        parts = []
        used = set()
        for chain, unit in found:
            part = doctree.deepcopy()
            path = [part.next_node(docutils.nodes.section)]
            if chain:
                path += [locate(part, u) for u in chain[1:] + (unit,)]

            # Units leading to the sub-section keep their own content, or only
            # their heading if they have many sub-units. The sub-section keeps
            # its own content. (chain holds the original parents.)
            for parent, node, next_node in zip(chain, path, path[1:]):
                few = len(self.child_units(parent)) <= self._split_leadin_limit
                context = self.own_content(node) if few else []
                self.rebuild(node, [*context, next_node])
            self.rebuild(path[-1], self.own_content(path[-1]))

            part_title = path[0].next_node(docutils.nodes.title)
            part.attributes["split_docname"] = docname
            part.attributes["split_title"] = (
                self.unit_title(unit) or part_title.astext()
            )
            if chain:
                anchor = self.unit_id(unit)
                part.attributes["split_anchor"] = anchor
                parts.append((self.part_name(docname, anchor, used), part))
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
