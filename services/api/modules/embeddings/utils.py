"""
Embedding utility functions.

Feature 2.3: Embedding Generation
"""
import math
from typing import List


def normalize_embedding(embedding: List[float]) -> List[float]:
    """
    Normalize embedding to unit L2 norm for cosine similarity.

    Args:
        embedding: Raw embedding vector

    Returns:
        Normalized embedding with L2 norm of 1.0
    """
    if not embedding:
        return embedding

    # Calculate L2 norm
    norm = math.sqrt(sum(x * x for x in embedding))

    # Handle zero vector
    if norm == 0:
        return embedding

    # Normalize
    return [x / norm for x in embedding]
