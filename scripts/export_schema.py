"""Export the canonical Python contract for the Node renderer."""

import json
import sys
from pathlib import Path

from slidemind_schemas.page import DeckSpec

target = Path(__file__).resolve().parents[1] / "packages/schemas/deck.schema.json"
schema = DeckSpec.model_json_schema()
schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
output = json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
if "--check" in sys.argv:
    if not target.exists() or target.read_text(encoding="utf-8") != output:
        sys.exit("Schema is out of date. Run npm run schema:export.")
else:
    target.write_text(output, encoding="utf-8")
    print(target)
