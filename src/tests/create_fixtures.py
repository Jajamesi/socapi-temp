import asyncio
import os
import json
from pathlib import Path

import dotenv
import socapi


dotenv.load_dotenv()

login = os.getenv("LOGIN", "")
password = os.getenv("PASSWORD", "")
test_poll = int(os.getenv("TEST_POLL", ""))

fixtures_dir = Path("fixtures")
fixtures_dir.mkdir(parents=True, exist_ok=True)


def metadata_to_dict(metadata):
    return {
        "variable_labels": metadata.variable_labels,
        "variable_value_labels": metadata.variable_value_labels,
        "variable_formats": metadata.variable_formats,
        "variable_measures": metadata.variable_measures,
        "variable_alignments": metadata.variable_alignments,
        "variable_display_widths": metadata.variable_display_widths,
    }

async def main():
    async with socapi.ParserClient(login=login, password=password, host="online-sociology.ru",) as client:
        # Получаем опрос
        poll = await client.poll.get_poll_structure(poll_id=test_poll)

        # Получаем SPSS metadata
        metadata = poll.spss_metadata

        # Сохраняем metadata
        with open(
            fixtures_dir / "spss_metadata.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                metadata_to_dict(metadata),
                f,
                ensure_ascii=False,
                indent=4
            )

        # Строим Polars schema на основе metadata
        schema = poll.formats_to_polars_schema(
            metadata.variable_formats
        )

        # Polars dtype преобразуем в строку, чтобы можно было сохранить в JSON
        schema_for_json = {
            name: str(dtype)
            for name, dtype in schema.items()
        }

        # Сохраняем schema
        with open(
            fixtures_dir / "polars_schema.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                schema_for_json,
                f,
                ensure_ascii=False,
                indent=4,
                sort_keys=True,
            )

    print("Fixtures saved.")

asyncio.run(main())