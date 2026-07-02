from app.modules.core.registry import (
    MODULE_REGISTRY,
)


async def ingest_dump(
    db,
    module,
    file_path,
    dra_type,
    instance_label,
):
    config = MODULE_REGISTRY[module]

    parser = __import__(config["parser"], fromlist=["parse_dump"],
                        )

    parsed = await parser.parse_dump(file_path)

    return parsed