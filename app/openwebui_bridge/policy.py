"""Pinned native settings required before classroom runtime initialization."""
POLICY = {
    'ui.enable_signup': False, 'oauth.enable_signup': False,
    'openai.enable': False, 'ollama.enable': False, 'evaluation.arena.enable': False,
    'task.title.enable': False, 'task.tags.enable': False, 'task.follow_up.enable': False,
    'rag.embedding_model': '', 'rag.bypass_embedding_and_retrieval': True, 'rag.enable_hybrid_search': False,
    'web.search.enable': False, 'code_execution.enable': False,
    'image_generation.enable': False, 'images.edit.enable': False,
}


def install_policy_hook(native):
    original = native.initialize_runtime_config
    async def initialize(app):
        from open_webui.models.config import Config
        await Config.upsert(POLICY)
        await original(app)
    native.initialize_runtime_config = initialize
