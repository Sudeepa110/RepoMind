"""
Unit tests for Conversation Service (Phase 7).
Tests repository-scoped conversation persistence, message ordering,
repository isolation, auto-titling, and recent history truncation.
"""

import pytest
from sqlalchemy import select

from backend.app.database.session import AsyncSessionLocal, init_db
from backend.app.database.models import RepositoryModel
from backend.app.llm.conversation_service import ConversationService
from backend.app.llm.generation_models import Citation


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.fixture
async def sample_repos():
    async with AsyncSessionLocal() as session:
        check1 = await session.execute(select(RepositoryModel).where(RepositoryModel.id == "repo-alpha"))
        if not check1.scalar_one_or_none():
            session.add(RepositoryModel(
                id="repo-alpha",
                owner="alpha-org",
                name="alpha-repo",
                url="https://github.com/alpha-org/alpha-repo",
                status="ready",
            ))
        check2 = await session.execute(select(RepositoryModel).where(RepositoryModel.id == "repo-beta"))
        if not check2.scalar_one_or_none():
            session.add(RepositoryModel(
                id="repo-beta",
                owner="beta-org",
                name="beta-repo",
                url="https://github.com/beta-org/beta-repo",
                status="ready",
            ))
        await session.commit()
    return "repo-alpha", "repo-beta"


@pytest.mark.asyncio
async def test_create_and_list_conversations(sample_repos):
    repo_a, repo_b = sample_repos
    service = ConversationService()

    async with AsyncSessionLocal() as session:
        c1 = await service.create_conversation(session, repository_id=repo_a, title="First Chat")
        c2 = await service.create_conversation(session, repository_id=repo_a, title="Second Chat")
        c_b = await service.create_conversation(session, repository_id=repo_b, title="Beta Chat")

        assert c1.id is not None
        assert c1.repository_id == repo_a
        assert c1.title == "First Chat"

        # List conversations for repo-alpha
        list_a = await service.list_conversations(session, repository_id=repo_a)
        assert len(list_a) >= 2
        titles_a = [item.title for item in list_a]
        assert "First Chat" in titles_a
        assert "Second Chat" in titles_a
        assert "Beta Chat" not in titles_a

        # List conversations for repo-beta
        list_b = await service.list_conversations(session, repository_id=repo_b)
        titles_b = [item.title for item in list_b]
        assert "Beta Chat" in titles_b
        assert "First Chat" not in titles_b


@pytest.mark.asyncio
async def test_repository_isolation_enforcement(sample_repos):
    repo_a, repo_b = sample_repos
    service = ConversationService()

    async with AsyncSessionLocal() as session:
        conv_a = await service.create_conversation(session, repository_id=repo_a, title="Secret Alpha")

        # Attempting to fetch conv_a using repo_b must return None
        fetched_cross = await service.get_conversation(session, repository_id=repo_b, conversation_id=conv_a.id)
        assert fetched_cross is None

        # Fetching with genuine repository_id succeeds
        fetched_valid = await service.get_conversation(session, repository_id=repo_a, conversation_id=conv_a.id)
        assert fetched_valid is not None
        assert fetched_valid.id == conv_a.id


@pytest.mark.asyncio
async def test_add_messages_and_auto_titling(sample_repos):
    repo_a, _ = sample_repos
    service = ConversationService()

    async with AsyncSessionLocal() as session:
        conv = await service.create_conversation(session, repository_id=repo_a)
        assert conv.title == "New Conversation"

        # Add first user message
        user_msg = await service.add_message(
            db=session,
            conversation_id=conv.id,
            repository_id=repo_a,
            role="user",
            content="Where is the JWT token verified in this project?",
        )
        assert user_msg.role == "user"

        # Conversation title should be auto-updated from default
        detail = await service.get_conversation(session, repository_id=repo_a, conversation_id=conv.id)
        assert "JWT token verified" in detail.title

        # Add assistant response with citations
        citation = Citation(
            citation_id="cite_1",
            file_path="src/security/jwt.py",
            start_line=15,
            end_line=32,
            symbol_name="decode_jwt",
            retrieval_source="HYBRID",
            confidence=0.95,
        )
        asst_msg = await service.add_message(
            db=session,
            conversation_id=conv.id,
            repository_id=repo_a,
            role="assistant",
            content="JWT tokens are decoded and validated in `decode_jwt` [src/security/jwt.py:15-32].",
            citations=[citation],
            confidence=0.95,
        )
        assert asst_msg.role == "assistant"
        assert len(asst_msg.citations) == 1
        assert asst_msg.citations[0].file_path == "src/security/jwt.py"

        # Verify full message sequence
        detail_after = await service.get_conversation(session, repository_id=repo_a, conversation_id=conv.id)
        assert len(detail_after.messages) == 2
        assert detail_after.messages[0].role == "user"
        assert detail_after.messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_get_recent_history_bounding(sample_repos):
    repo_a, _ = sample_repos
    service = ConversationService()

    async with AsyncSessionLocal() as session:
        conv = await service.create_conversation(session, repository_id=repo_a, title="Long Chat")

        # Add 10 messages
        for i in range(10):
            role = "user" if i % 2 == 0 else "assistant"
            await service.add_message(
                db=session,
                conversation_id=conv.id,
                repository_id=repo_a,
                role=role,
                content=f"Message {i}",
            )

        # Retrieve last 4 turns
        history = await service.get_recent_history(session, conversation_id=conv.id, max_messages=4)
        assert len(history) == 4
        # Chronological order
        assert history[0]["content"] == "Message 6"
        assert history[1]["content"] == "Message 7"
        assert history[2]["content"] == "Message 8"
        assert history[3]["content"] == "Message 9"


@pytest.mark.asyncio
async def test_delete_conversation(sample_repos):
    repo_a, repo_b = sample_repos
    service = ConversationService()

    async with AsyncSessionLocal() as session:
        conv = await service.create_conversation(session, repository_id=repo_a, title="To Delete")

        # Wrong repo cannot delete
        res_fail = await service.delete_conversation(session, repository_id=repo_b, conversation_id=conv.id)
        assert res_fail is False

        # Correct repo deletes successfully
        res_ok = await service.delete_conversation(session, repository_id=repo_a, conversation_id=conv.id)
        assert res_ok is True

        # Verify it's gone
        after = await service.get_conversation(session, repository_id=repo_a, conversation_id=conv.id)
        assert after is None
