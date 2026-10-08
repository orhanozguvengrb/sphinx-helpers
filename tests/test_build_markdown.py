"""Test the build process with Text builder with the test root."""

import json
import pathlib
import shutil
import textwrap

import pytest

here = pathlib.Path(__file__).parent.resolve()
reference_dir = here / "reference"


def assert_exists(fp):
    assert fp.exists(), f"Missing expected file {fp.parts[-1]}"


def assert_not_exists(fp):
    assert not fp.exists(), f"Found unexpected file {fp.parts[-1]}"


@pytest.mark.sphinx(buildername="markdown", testroot=here / "markdown-only")
def test_markdown_only(app, status, warning):
    output_dir = pathlib.Path(app.outdir)
    assert output_dir.parts[-2] == "_build"
    assert output_dir.parts[-1] == "markdown"

    shutil.rmtree(output_dir.parent, ignore_errors=True)
    app.build()

    assert_exists(output_dir.joinpath("doc1.md"))
    assert_not_exists(output_dir.joinpath("doc1.md.metadata.json"))
    assert_not_exists(output_dir.joinpath("doc1.html"))
    assert_not_exists(output_dir.joinpath("doc1.txt"))

    for file_path in ["doc1.md", "code.md"]:
        content = output_dir.joinpath(file_path).read_text()
        expected_content = reference_dir.joinpath(file_path).read_text()
        assert content == expected_content


@pytest.mark.sphinx(buildername="markdown", testroot=here / "markdown-with-metadata")
def test_markdown_with_metadata(app, status, warning):
    output_dir = pathlib.Path(app.outdir)
    assert output_dir.parts[-2] == "_build"
    assert output_dir.parts[-1] == "markdown"

    shutil.rmtree(output_dir.parent, ignore_errors=True)
    app.build()

    assert_exists(output_dir.joinpath("doc1.md"))
    assert_exists(output_dir.joinpath("doc1.md.metadata.json"))
    assert_not_exists(output_dir.joinpath("doc1.html"))
    assert_not_exists(output_dir.joinpath("doc1.txt"))

    for file_path in ["doc1.md"]:
        content = output_dir.joinpath(file_path).read_text()
        expected_content = reference_dir.joinpath(file_path).read_text()
        assert content == expected_content

    for file_path in ["doc1.md.metadata.json", "index.md.metadata.json"]:
        content = json.loads(output_dir.joinpath(file_path).read_text())
        expected_content = json.loads(reference_dir.joinpath(file_path).read_text())
        assert content == expected_content


@pytest.mark.sphinx(
    buildername="markdown", testroot=here / "markdown-with-metadata-title"
)
def test_markdown_with_metadata_title(app, status, warning):
    output_dir = pathlib.Path(app.outdir)
    assert output_dir.parts[-2] == "_build"
    assert output_dir.parts[-1] == "markdown"

    shutil.rmtree(output_dir.parent, ignore_errors=True)
    app.build()

    assert_exists(output_dir.joinpath("doc1.md"))
    assert_exists(output_dir.joinpath("doc1.md.metadata.json"))
    assert_exists(output_dir.joinpath("index.md.metadata.json"))
    assert_not_exists(output_dir.joinpath("doc1.html"))
    assert_not_exists(output_dir.joinpath("doc1.txt"))

    for file_path in ["doc1.md"]:
        content = output_dir.joinpath(file_path).read_text()
        expected_content = reference_dir.joinpath(file_path).read_text()
        assert content == expected_content

    for file_path in ["doc1.md.metadata.json"]:
        content = json.loads(output_dir.joinpath(file_path).read_text())
        expected_content = json.loads(
            reference_dir.joinpath(file_path + ".alt").read_text()
        )
        assert content == expected_content

    for file_path in ["index.md.metadata.json"]:
        content = json.loads(output_dir.joinpath(file_path).read_text())
        expected_content = json.loads(reference_dir.joinpath(file_path).read_text())
        assert content == expected_content


@pytest.mark.sphinx(buildername="markdown", testroot=here / "markdown-with-header")
def test_markdown_with_header(app, status, warning):
    output_dir = pathlib.Path(app.outdir)
    assert output_dir.parts[-2] == "_build"
    assert output_dir.parts[-1] == "markdown"

    shutil.rmtree(output_dir.parent, ignore_errors=True)
    app.build()

    assert_exists(output_dir.joinpath("doc1.md"))
    assert_not_exists(output_dir.joinpath("doc1.md.metadata.json"))
    assert_not_exists(output_dir.joinpath("doc1.html"))
    assert_not_exists(output_dir.joinpath("doc1.txt"))

    file_path = "doc1.md"
    content = output_dir.joinpath(file_path).read_text()
    expected_body = reference_dir.joinpath(file_path).read_text()
    expected_header = textwrap.dedent(
        """
        ---
        title: Section A
        url: /path/to/site_root/doc1.md
        ---

        """
    ).lstrip()
    expected_content = expected_header + expected_body
    assert content == expected_content


@pytest.mark.sphinx(buildername="markdown", testroot=here / "markdown-split-sections")
def test_markdown_split_sections(app, status, warning):
    output_dir = pathlib.Path(app.outdir)
    assert output_dir.parts[-2] == "_build"
    assert output_dir.parts[-1] == "markdown"

    shutil.rmtree(output_dir.parent, ignore_errors=True)
    app.build()

    # Pages with sub-sections are written as one file for the page itself (its
    # title and own content, with the url of the page) and one per sub-section
    for docname in ["few", "many"]:
        assert_exists(output_dir.joinpath(f"{docname}.md"))
        content = output_dir.joinpath(f"{docname}.md").read_text()
        expected_content = reference_dir.joinpath(f"{docname}.md").read_text()
        assert content == expected_content

        metadata = json.loads(
            output_dir.joinpath(f"{docname}.md.metadata.json").read_text()
        )
        attributes = metadata["metadataAttributes"]
        title = attributes["title"]["value"]["stringValue"]
        assert title == f"{docname.title()} Sections"
        assert (
            attributes["x-amz-bedrock-kb-source-uri"]["value"]["stringValue"]
            == f"/path/to/site_root/{docname}.html"
        )

    # A page without sub-sections is unchanged
    assert_exists(output_dir.joinpath("single.md"))
    assert_exists(output_dir.joinpath("single.md.metadata.json"))

    # Every content file has a metadata file with a non-empty title and an
    # anchored url, and vice versa
    for docname, anchors in [
        ("few", ["alpha", "beta"]),
        ("many", ["alpha", "beta", "gamma", "delta"]),
    ]:
        for anchor in anchors:
            part = f"{docname}__{anchor}"
            assert_exists(output_dir.joinpath(f"{part}.md"))
            assert_exists(output_dir.joinpath(f"{part}.md.metadata.json"))

            content = output_dir.joinpath(f"{part}.md").read_text()
            expected_content = reference_dir.joinpath(f"{part}.md").read_text()
            assert content == expected_content

            metadata = json.loads(
                output_dir.joinpath(f"{part}.md.metadata.json").read_text()
            )
            attributes = metadata["metadataAttributes"]
            assert attributes["title"]["value"]["stringValue"] == anchor.title()
            assert (
                attributes["x-amz-bedrock-kb-source-uri"]["value"]["stringValue"]
                == f"/path/to/site_root/{docname}.html#{anchor}"
            )


@pytest.mark.sphinx(
    buildername="markdown",
    testroot=here / "markdown-split-sections",
    confoverrides={"markdown_split_leadin_limit": 4},
)
def test_markdown_split_sections_leadin_limit(app, status, warning):
    output_dir = pathlib.Path(app.outdir)
    assert output_dir.parts[-2] == "_build"
    assert output_dir.parts[-1] == "markdown"

    shutil.rmtree(output_dir.parent, ignore_errors=True)
    app.build()

    # "many" has exactly 4 sub-sections, so the lead-in is kept at the limit
    content = output_dir.joinpath("many__gamma.md").read_text()
    expected_content = textwrap.dedent(
        """
        # Many Sections

        Lead-in text that is not repeated.

        ## Gamma

        Text of gamma.
        """
    ).lstrip()
    assert content == expected_content


@pytest.mark.sphinx(
    buildername="markdown",
    testroot=here / "markdown-split-sections",
    confoverrides={"markdown_include_header": True},
)
def test_markdown_split_sections_with_header(app, status, warning):
    output_dir = pathlib.Path(app.outdir)
    assert output_dir.parts[-2] == "_build"
    assert output_dir.parts[-1] == "markdown"

    shutil.rmtree(output_dir.parent, ignore_errors=True)
    app.build()

    file_path = "few__beta.md"
    content = output_dir.joinpath(file_path).read_text()
    expected_body = reference_dir.joinpath(file_path).read_text()
    expected_header = textwrap.dedent(
        """
        ---
        title: Few Sections
        url: /path/to/site_root/few__beta.md
        ---

        """
    ).lstrip()
    assert content == expected_header + expected_body


@pytest.mark.sphinx(
    buildername="markdown",
    testroot=here / "markdown-split-sections",
    confoverrides={"markdown_split_leadin_limit": 20},
)
def test_markdown_split_sections_nested(app, status, warning):
    output_dir = pathlib.Path(app.outdir)
    assert output_dir.parts[-2] == "_build"
    assert output_dir.parts[-1] == "markdown"

    shutil.rmtree(output_dir.parent, ignore_errors=True)
    app.build()

    # Sub-sections are split at every depth. Each part has the sections
    # leading to it with their content, and its own content only
    anchors = ["outer", "inner-one", "inner-two", "deepest", "sibling"]
    for part in ["nested"] + [f"nested__{a}" for a in anchors]:
        assert_exists(output_dir.joinpath(f"{part}.md"))
        assert_exists(output_dir.joinpath(f"{part}.md.metadata.json"))

        content = output_dir.joinpath(f"{part}.md").read_text()
        expected_content = reference_dir.joinpath(f"{part}.md").read_text()
        assert content == expected_content

    # A section with no content of its own is not written
    assert_not_exists(output_dir.joinpath("nested__empty-parent.md"))
    assert_not_exists(output_dir.joinpath("nested__empty-parent.md.metadata.json"))

    metadata = json.loads(
        output_dir.joinpath("nested__deepest.md.metadata.json").read_text()
    )
    attributes = metadata["metadataAttributes"]
    assert attributes["title"]["value"]["stringValue"] == "Deepest"
    assert (
        attributes["x-amz-bedrock-kb-source-uri"]["value"]["stringValue"]
        == "/path/to/site_root/nested.html#deepest"
    )


@pytest.mark.sphinx(
    buildername="markdown",
    testroot=here / "markdown-split-sections",
    confoverrides={"markdown_split_leadin_limit": 1},
)
def test_markdown_split_sections_nested_many(app, status, warning):
    output_dir = pathlib.Path(app.outdir)
    assert output_dir.parts[-2] == "_build"
    assert output_dir.parts[-1] == "markdown"

    shutil.rmtree(output_dir.parent, ignore_errors=True)
    app.build()

    # The page and "Outer" each have 2 sub-sections, more than the limit of 1,
    # so their content is dropped and only their titles are kept. "Inner Two"
    # has a single sub-section, so its content is kept.
    content = output_dir.joinpath("nested__deepest.md").read_text()
    expected_content = textwrap.dedent(
        """
        # Nested Page

        ## Outer

        ### Inner Two

        Text of inner two.

        #### Deepest

        Text of deepest.
        """
    ).lstrip()
    assert content == expected_content


@pytest.mark.sphinx(buildername="markdown", testroot=here / "markdown-split-sections")
def test_markdown_split_sections_objects(app, status, warning):
    output_dir = pathlib.Path(app.outdir)
    assert output_dir.parts[-2] == "_build"
    assert output_dir.parts[-1] == "markdown"

    shutil.rmtree(output_dir.parent, ignore_errors=True)
    app.build()

    # Object descriptions with an anchor (functions, classes, methods) are
    # split like sections, and can be nested
    expected = {
        "api": ("API Page", "api.html"),
        "api__c.api_one": ("api_one", "api.html#c.api_one"),
        "api__c.api_two": ("api_two", "api.html#c.api_two"),
        "api__Widget": ("Widget", "api.html#Widget"),
        "api__Widget.run": ("run", "api.html#Widget.run"),
    }
    for part, (title, url) in expected.items():
        assert_exists(output_dir.joinpath(f"{part}.md"))

        content = output_dir.joinpath(f"{part}.md").read_text()
        expected_content = reference_dir.joinpath(f"{part}.md").read_text()
        assert content == expected_content

        metadata = json.loads(
            output_dir.joinpath(f"{part}.md.metadata.json").read_text()
        )
        attributes = metadata["metadataAttributes"]
        assert attributes["title"]["value"]["stringValue"] == title
        assert (
            attributes["x-amz-bedrock-kb-source-uri"]["value"]["stringValue"]
            == f"/path/to/site_root/{url}"
        )


@pytest.mark.sphinx(buildername="markdown", testroot=here / "markdown-split-c-api")
def test_markdown_split_sections_c_api(app, status, warning):
    output_dir = pathlib.Path(app.outdir)
    assert output_dir.parts[-2] == "_build"
    assert output_dir.parts[-1] == "markdown"

    shutil.rmtree(output_dir.parent, ignore_errors=True)
    app.build()

    # The page has no sections, only function entries (modelled on the C
    # callback reference page). The page has no text of its own, so it has
    # no file; each function has one, with the url of its anchor.
    assert_not_exists(output_dir.joinpath("callback.md"))
    assert_not_exists(output_dir.joinpath("callback.md.metadata.json"))

    base_url = "https://docs.gurobi.com/projects/optimizer/en/current/reference/c"
    for name in ["GRBcbsetdblparam", "GRBcbsetintparam", "GRBcbcut", "GRBterminate"]:
        part = f"callback__c.{name}"
        assert_exists(output_dir.joinpath(f"{part}.md"))

        content = output_dir.joinpath(f"{part}.md").read_text()
        expected_content = reference_dir.joinpath(f"{part}.md").read_text()
        assert content == expected_content

        metadata = json.loads(
            output_dir.joinpath(f"{part}.md.metadata.json").read_text()
        )
        attributes = metadata["metadataAttributes"]
        assert attributes["title"]["value"]["stringValue"] == name
        assert (
            attributes["x-amz-bedrock-kb-source-uri"]["value"]["stringValue"]
            == f"{base_url}/callback.html#c.{name}"
        )
