"""
RAG (Retrieval-Augmented Generation) Service.

Provides vector-based similarity search for finding similar historical cases.
Uses pgvector for efficient nearest-neighbor search in PostgreSQL.

This feature can be disabled with RAG_ENABLED=false in environment.
"""

import logging
from typing import Optional

from openai import OpenAI
from sqlmodel import Session, select
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models import AnalysisResult
from app.services.secret_manager import get_settings

logger = logging.getLogger(__name__)


class RAGService:
    """
    Service for RAG-based similarity search.
    
    Generates embeddings using OpenAI's text-embedding-3-small model
    and performs vector similarity search using pgvector.
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()
        self._client: Optional[OpenAI] = None
        
    @property
    def is_enabled(self) -> bool:
        """Check if RAG is enabled in settings."""
        return self.settings.rag_enabled
    
    @property
    def client(self) -> OpenAI:
        """Lazy-initialize OpenAI client for embeddings."""
        if self._client is None:
            # Use OpenAI API for embeddings (works regardless of LLM provider)
            # Azure OpenAI also supports embeddings, but OpenAI is simpler for demo
            api_key = self.settings.openai_api_key
            if not api_key:
                # Fallback to Azure OpenAI key if available
                api_key = self.settings.azure_openai_api_key
            
            if not api_key:
                raise ValueError(
                    "RAG requires OPENAI_API_KEY or AZURE_OPENAI_API_KEY for embeddings"
                )
            
            self._client = OpenAI(api_key=api_key)
        
        return self._client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def get_embedding(self, text: str) -> list[float]:
        """
        Generate embedding vector for text using OpenAI.
        
        Args:
            text: Text to embed (max ~8000 tokens)
            
        Returns:
            List of floats (1536 dimensions for text-embedding-3-small)
        """
        if not self.is_enabled:
            return []
        
        response = self.client.embeddings.create(
            input=text,
            model=self.settings.embedding_model,
        )
        
        return response.data[0].embedding
    
    def embed_result(self, result: AnalysisResult, input_text: str) -> None:
        """
        Generate and store embedding for an analysis result.
        
        Embeds a combination of input text and analysis result
        to capture both the original case and the outcome.
        
        Args:
            result: AnalysisResult to embed
            input_text: Original input text from request
        """
        if not self.is_enabled:
            logger.debug("RAG disabled, skipping embedding generation")
            return
        
        try:
            # Create embedding text combining input and output
            # This allows searching by similar inputs OR similar outcomes
            embed_text = f"""
Input: {input_text}
Score: {result.score}
Categories: {', '.join(result.categories)}
Summary: {result.summary[:500]}
"""
            
            embedding = self.get_embedding(embed_text.strip())
            result.embedding = embedding
            
            logger.info(f"Generated embedding for result {result.id}")
            
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            # Don't fail the whole operation if embedding fails
    
    def find_similar_cases(
        self,
        query_text: str,
        limit: int = 3,
        exclude_result_id: Optional[int] = None,
    ) -> list[AnalysisResult]:
        """
        Find similar historical cases using vector similarity search.
        
        Uses cosine distance (<=>) for semantic similarity matching.
        
        Args:
            query_text: Text to find similar cases for
            limit: Maximum number of results (default 3)
            exclude_result_id: Result ID to exclude (e.g., current result)
            
        Returns:
            List of similar AnalysisResult objects, ordered by similarity
        """
        if not self.is_enabled:
            logger.debug("RAG disabled, returning empty results")
            return []
        
        try:
            # Generate embedding for query
            query_embedding = self.get_embedding(query_text)
            
            # Build query with vector similarity ordering
            # Using l2_distance (Euclidean) - also supports cosine_distance
            # Note: This requires the pgvector extension and Vector column
            from sqlalchemy import text
            
            # Raw SQL for vector similarity (SQLModel doesn't have native support)
            # Using <=> operator for cosine distance (lower = more similar)
            stmt = text("""
                SELECT id, request_id, score, categories, summary,
                       processed_content, model_version, "group",
                       analyzed_by_user_id, llm_trace, human_feedback,
                       feedback_comment, feedback_by_user_id, feedback_at,
                       validation_status, validation_details, created_at,
                       embedding <=> :query_vec AS distance
                FROM analysis_results
                WHERE embedding IS NOT NULL
                  AND (:exclude_id IS NULL OR id != :exclude_id)
                ORDER BY embedding <=> :query_vec
                LIMIT :limit
            """)
            
            # Format embedding as PostgreSQL array literal
            vec_literal = f"[{','.join(map(str, query_embedding))}]"
            
            result = self.session.exec(
                stmt.bindparams(
                    query_vec=vec_literal,
                    exclude_id=exclude_result_id,
                    limit=limit,
                )
            )
            
            # Fetch and convert to AnalysisResult objects
            similar_results = []
            for row in result:
                # Re-fetch full AnalysisResult object
                analysis_result = self.session.get(AnalysisResult, row.id)
                if analysis_result:
                    similar_results.append(analysis_result)
            
            logger.info(f"Found {len(similar_results)} similar cases")
            return similar_results
            
        except Exception as e:
            logger.warning(f"Similarity search failed: {e}")
            return []
    
    def find_similar_to_result(
        self,
        result: AnalysisResult,
        limit: int = 3,
    ) -> list[AnalysisResult]:
        """
        Find cases similar to an existing analysis result.
        
        Convenience method that constructs query text from result.
        
        Args:
            result: AnalysisResult to find similar cases for
            limit: Maximum number of results
            
        Returns:
            List of similar AnalysisResult objects
        """
        if not self.is_enabled:
            return []
        
        # Get input text from request
        request = result.request
        if not request:
            return []
        
        query_text = f"{request.input_text} - {result.summary[:200]}"
        
        return self.find_similar_cases(
            query_text=query_text,
            limit=limit,
            exclude_result_id=result.id,
        )


def get_rag_service(session: Session) -> RAGService:
    """Factory function for RAG service."""
    return RAGService(session)

