from ..builders import MarkdownBuilder


def setup(app):
    app.add_builder(MarkdownBuilder)
    app.add_config_value("markdown_include_metadata", default=False, rebuild="env")
    app.add_config_value("markdown_include_header", default=False, rebuild="env")
    app.add_config_value("metadata_use_title_attribute", default=False, rebuild="env")
    app.add_config_value("markdown_split_sections", default=False, rebuild="env")
    app.add_config_value("markdown_split_leadin_limit", default=20, rebuild="env")
