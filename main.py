def load_knowledge():
    knowledge_parts = []
    knowledge_folder = "knowledge"

    try:
        for filename in sorted(os.listdir(knowledge_folder)):
            if filename.endswith(".txt"):
                file_path = os.path.join(knowledge_folder, filename)

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()

                if content:
                    knowledge_parts.append(
                        f"\n=== ФАЙЛ БАЗЫ: {filename} ===\n{content}"
                    )

        print(
            f"Knowledge loaded: {len(knowledge_parts)} files",
            flush=True
        )

        return "\n\n".join(knowledge_parts)

    except Exception as e:
        print("Knowledge error:", repr(e), flush=True)
        return ""

KNOWLEDGE = load_knowledge()
