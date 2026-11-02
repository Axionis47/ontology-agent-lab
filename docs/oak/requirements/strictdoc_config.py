"""Native StrictDoc configuration for the OaK requirement sources."""

from strictdoc.core.project_config import ProjectConfig


def create_config():
    return ProjectConfig(
        project_title="OaK requirements and contracts",
        exclude_doc_paths=["*.md", "**/*.md"],
    )
