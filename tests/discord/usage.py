"""Collect application and learner usage for a Discord test conversation."""

from pathlib import Path

from sqlalchemy import select

from evaluation.pricing import summarize_usage
from src.storage.sql_connection import create_sql_session
from src.storage.sql_metrics import UsageModel

APPLICATION_ROOT = Path(__file__).resolve().parents[2]


def conversation_cost_report(testerbot, rubber_duck_config):
    if testerbot.last_context is None:
        raise RuntimeError("TesterBot did not create a DuckContext.")

    conversation_id = testerbot.last_context.conversation_id
    tester_rows = [
        row for row in testerbot.usage_collector.rows
        if row["conversation_id"] == conversation_id
    ]

    sql_config = dict(rubber_duck_config["sql"])
    database_path = Path(sql_config["database"])
    if not database_path.is_absolute():
        database_path = APPLICATION_ROOT / database_path
    sql_config["database"] = str(database_path)

    session = create_sql_session(sql_config)
    try:
        duck_rows = [
            {
                "conversation_id": row.conversation_id,
                "model": row.engine,
                "input_tokens": int(row.input_tokens or 0),
                "output_tokens": int(row.output_tokens or 0),
                "cached_tokens": int(row.cached_tokens or 0),
                "reasoning_tokens": int(row.reasoning_tokens or 0),
            }
            for row in session.scalars(
                select(UsageModel).where(UsageModel.conversation_id == conversation_id)
            )
        ]
    finally:
        session.close()

    tester_summary = summarize_usage(tester_rows)
    duck_summary = summarize_usage(duck_rows)
    total = summarize_usage(tester_rows + duck_rows)
    report = {
        "tester_bot": tester_summary,
        "rubber_duck": duck_summary,
        "total": total,
    }
    print(f"\nConversation usage (conversation {conversation_id})")
    print(
        f"  tester bot: tokens={tester_summary['input_tokens'] + tester_summary['output_tokens']} "
        f"(input={tester_summary['input_tokens']}, "
        f"output={tester_summary['output_tokens']}), "
        f"cost=${tester_summary['cost_usd']:.6f}"
    )
    print(
        f"  rubber duck: tokens={duck_summary['input_tokens'] + duck_summary['output_tokens']} "
        f"(input={duck_summary['input_tokens']}, "
        f"output={duck_summary['output_tokens']}), "
        f"cost=${duck_summary['cost_usd']:.6f}"
    )
    print(
        f"  total: tokens={total['input_tokens'] + total['output_tokens']} "
        f"(input={total['input_tokens']}, output={total['output_tokens']}), "
        f"cost=${total['cost_usd']:.6f}"
    )
    return report
