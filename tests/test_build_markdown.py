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

    # Pages with sub-sections are replaced by one file per sub-section
    assert_not_exists(output_dir.joinpath("few.md"))
    assert_not_exists(output_dir.joinpath("few.md.metadata.json"))
    assert_not_exists(output_dir.joinpath("many.md"))
    assert_not_exists(output_dir.joinpath("many.md.metadata.json"))

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
