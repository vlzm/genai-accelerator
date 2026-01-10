"""
RAG (Retrieval-Augmented Generation) Service.

Provides vector-based similarity search for finding similar historical cases.
Uses pgvector for efficient nearest-neighbor search in PostgreSQL.

This feature can be disabled with RAG_ENABLED=false in environment.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI
from sqlmodel import Session, select
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models import AnalysisResult
from app.services.secret_manager import get_settings

logger = logging.getLogger(__name__)


def calculate_similarity(
    embedding1: list[float],
    embedding2: list[float],
) -> tuple[float, float]:
    """
    Calculate similarity between two embeddings using the same logic as pgvector.
    
    This replicates the behavior of PostgreSQL's cosine distance operator (<=>).
    Uses cosine similarity directly for intuitive percentage interpretation.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Tuple of (cosine_distance, similarity_pct)
        - cosine_distance: 0 (identical) to 2 (opposite)
        - similarity_pct: 0% (unrelated/opposite) to 100% (identical)
        
    Example:
        >>> emb1 = [0.1, 0.2, 0.3]
        >>> emb2 = [0.1, 0.2, 0.3]
        >>> distance, similarity = calculate_similarity(emb1, emb2)
        >>> distance  # Should be ~0.0 (identical)
        >>> similarity  # Should be ~100.0%
        
        >>> # Unrelated texts will give ~0% similarity
        >>> # Similar texts will give >50% similarity
    """
    if len(embedding1) != len(embedding2):
        raise ValueError(
            f"Embeddings must have the same dimension: "
            f"{len(embedding1)} vs {len(embedding2)}"
        )
    
    # Calculate dot product
    dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
    
    # Calculate norms (L2 norm)
    norm1 = math.sqrt(sum(x * x for x in embedding1))
    norm2 = math.sqrt(sum(x * x for x in embedding2))
    
    if norm1 == 0 or norm2 == 0:
        # Zero vector case - return maximum distance
        return 2.0, 0.0
    
    # Cosine similarity: dot_product / (norm1 * norm2)
    # Range: -1 (opposite) to 1 (identical)
    cosine_similarity = dot_product / (norm1 * norm2)
    
    # Cosine distance: 1 - cosine_similarity
    # This matches pgvector's <=> operator
    # Range: 0 (identical) to 2 (opposite)
    cosine_distance = 1.0 - cosine_similarity
    
    # Convert to similarity percentage using cosine similarity directly
    # This gives intuitive results:
    # - cosine_similarity = 1.0 → 100% (identical)
    # - cosine_similarity = 0.0 → 0% (unrelated/orthogonal)
    # - cosine_similarity < 0  → 0% (opposite, clamped)
    similarity_pct = max(0.0, cosine_similarity) * 100.0
    
    return cosine_distance, similarity_pct


@dataclass
class SimilarCaseResult:
    """
    Result of a similarity search with distance score.
    
    Attributes:
        result: The similar AnalysisResult
        distance: Cosine distance (0 = identical, 2 = opposite)
        similarity_pct: Similarity percentage (100% = identical)
    """
    result: AnalysisResult
    distance: float
    similarity_pct: float


@dataclass
class RAGTrace:
    """
    Trace information for RAG operations.
    
    Captures all details needed for debugging and understanding
    how RAG search worked.
    """
    enabled: bool = False
    query_text: str = ""
    query_text_truncated: str = ""
    embedding_model: str = ""
    embedding_dimensions: int = 0
    embedding_generated: bool = False
    embedding_error: Optional[str] = None
    search_performed: bool = False
    search_error: Optional[str] = None
    results_found: int = 0
    results_after_filter: int = 0
    similarity_threshold: float = 0.0
    results_details: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert trace to dictionary for JSON serialization."""
        return {
            "enabled": self.enabled,
            "query_text_preview": self.query_text_truncated,
            "embedding": {
                "model": self.embedding_model,
                "dimensions": self.embedding_dimensions,
                "generated": self.embedding_generated,
                "error": self.embedding_error,
            },
            "search": {
                "performed": self.search_performed,
                "error": self.search_error,
                "similarity_threshold_pct": self.similarity_threshold * 100,
            },
            "results": {
                "found_before_filter": self.results_found,
                "returned_after_filter": self.results_after_filter,
                "details": self.results_details,
            },
        }


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
        min_similarity: float = 0.3,
    ) -> tuple[list[SimilarCaseResult], RAGTrace]:
        """
        Find similar historical cases using vector similarity search.
        
        Uses cosine distance (<=>) for semantic similarity matching.
        
        Args:
            query_text: Text to find similar cases for
            limit: Maximum number of results (default 3)
            exclude_result_id: Result ID to exclude (e.g., current result)
            min_similarity: Minimum similarity threshold (0.0-1.0, default 0.3 = 30%)
            
        Returns:
            Tuple of (list of SimilarCaseResult with distance scores, RAGTrace)
        """
        trace = RAGTrace(
            enabled=self.is_enabled,
            query_text=query_text,
            query_text_truncated=query_text[:200] + "..." if len(query_text) > 200 else query_text,
            similarity_threshold=min_similarity,
        )
        
        if not self.is_enabled:
            logger.debug("RAG disabled, returning empty results")
            return [], trace
        
        try:
            # Generate embedding for query
            trace.embedding_model = self.settings.embedding_model
            query_embedding = self.get_embedding(query_text)
            trace.embedding_dimensions = len(query_embedding)
            trace.embedding_generated = True
            
            # Build query with vector similarity ordering
            from sqlalchemy import text
            
            # Raw SQL for vector similarity (SQLModel doesn't have native support)
            # Using <=> operator for cosine distance (lower = more similar)
            # Cosine distance range: 0 (identical) to 2 (opposite)
            # We fetch more than limit to allow filtering by threshold
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
                    limit=limit * 2,  # Fetch more to allow filtering
                )
            )
            
            trace.search_performed = True
            
            # Fetch and convert to SimilarCaseResult objects with distance
            similar_results = []
            all_results_info = []
            
            for row in result:
                distance = float(row.distance)
                # Convert cosine distance to similarity percentage
                # cosine_similarity = 1 - distance (range: -1 to 1)
                # similarity_pct uses cosine_similarity directly for intuitive results:
                # - distance = 0 → cosine_similarity = 1 → 100% (identical)
                # - distance = 1 → cosine_similarity = 0 → 0% (unrelated)
                # - distance = 2 → cosine_similarity = -1 → 0% (opposite, clamped)
                cosine_similarity = 1.0 - distance
                similarity_pct = max(0, cosine_similarity) * 100
                
                all_results_info.append({
                    "id": row.id,
                    "distance": round(distance, 4),
                    "similarity_pct": round(similarity_pct, 1),
                    "score": row.score,
                    "passed_threshold": similarity_pct >= min_similarity * 100,
                })
                
                # Filter by similarity threshold
                if similarity_pct >= min_similarity * 100 and len(similar_results) < limit:
                    analysis_result = self.session.get(AnalysisResult, row.id)
                    if analysis_result:
                        similar_results.append(SimilarCaseResult(
                            result=analysis_result,
                            distance=distance,
                            similarity_pct=similarity_pct,
                        ))
            
            trace.results_found = len(all_results_info)
            trace.results_after_filter = len(similar_results)
            trace.results_details = all_results_info
            
            logger.info(
                f"RAG search: found {trace.results_found} candidates, "
                f"{trace.results_after_filter} passed {min_similarity*100:.0f}% threshold"
            )
            return similar_results, trace
            
        except Exception as e:
            trace.search_error = str(e)
            logger.warning(f"Similarity search failed: {e}")
            return [], trace
    
    def find_similar_to_result(
        self,
        result: AnalysisResult,
        limit: int = 3,
        min_similarity: float = 0.3,
    ) -> tuple[list[SimilarCaseResult], RAGTrace]:
        """
        Find cases similar to an existing analysis result.
        
        Convenience method that constructs query text from result.
        
        Args:
            result: AnalysisResult to find similar cases for
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold (0.0-1.0)
            
        Returns:
            Tuple of (list of SimilarCaseResult, RAGTrace)
        """
        trace = RAGTrace(enabled=self.is_enabled)
        
        if not self.is_enabled:
            return [], trace
        
        # Get input text from request
        request = result.request
        if not request:
            trace.search_error = "No request associated with result"
            return [], trace
        
        query_text = f"{request.input_text} - {result.summary[:200]}"
        
        return self.find_similar_cases(
            query_text=query_text,
            limit=limit,
            exclude_result_id=result.id,
            min_similarity=min_similarity,
        )


def get_rag_service(session: Session) -> RAGService:
    """Factory function for RAG service."""
    return RAGService(session)

