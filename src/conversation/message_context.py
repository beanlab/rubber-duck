def generate_message_history_from_message_context(message_context: list[dict]):

    history = []

    for context_item in message_context:
        if is_file(context_item["content"]):
            context_item["content"] = create_file_item(context_item)

        history.append(
            GPTMessage(role=context_item.get("role"), content=context_item['content'])
        )

    return history
