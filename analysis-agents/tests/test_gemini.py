from llm.gemini import provider_schema
from schemas import Output
from llm.base import Reply
from agents.base import generate
from test_verification import pack, CONFIG, output
import pytest


def test_provider_schema_expands_refs_and_preserves_nullable_fields():
    schema = provider_schema(Output.model_json_schema())
    claim = schema["properties"]["claims"]["items"]
    assert claim["type"] == "OBJECT"
    assert claim["properties"]["value"] == {"type": "NUMBER", "nullable": True}
    assert "kind" in claim["required"] and "$ref" not in str(schema)
    assert "additionalProperties" not in str(schema)


def test_truncated_response_is_not_accepted_even_if_json_parses():
    class Limited:
        def generate(self, *args):
            return Reply(output().model_dump_json(), finish_reason="MAX_TOKENS")

    with pytest.raises(ValueError, match="provider response incomplete"):
        generate(Limited(), "bull", 1, pack(), [], CONFIG)
